from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from datetime import datetime

from .state import get_state, clear_state
from .scheduling import build_candidate_slots, format_spoken, PACIFIC
from .notify import send_owner_sms

router = APIRouter()

def as_xml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="text/xml")

def gather(action: str, prompt: str) -> Response:
    vr = VoiceResponse()
    g = Gather(input="speech", action=action, method="POST", speech_timeout="auto", language="en-US")
    g.say(prompt)
    vr.append(g)
    vr.say("Sorry, I didn’t catch that. Let’s try again.")
    vr.redirect("/voice/", method="POST")
    return as_xml(vr)

def norm(s: str) -> str:
    return (s or "").strip().lower()

def pick_first_or_second(s: str) -> int | None:
    s = norm(s)
    if any(x in s for x in ["first", "one", "1"]):
        return 1
    if any(x in s for x in ["second", "two", "2"]):
        return 2
    return None

@router.post("/")
async def voice_root(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    _ = get_state(call_sid)
    return gather("/voice/intent", "Hi, thanks for calling White’s Painting and Renovations here in Ukiah. This is Sally. Are you calling for a free estimate, a project update, or billing?")

@router.post("/intent")
async def voice_intent(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    s = norm(speech)
    if any(w in s for w in ["estimate", "quote", "pricing", "paint", "painting", "remodel"]):
        st.intent = "estimate"
        return gather("/voice/name", "Perfect. What’s your first and last name?")

    return gather("/voice/intent", "No problem—are you calling for a free estimate, a project update, or billing?")

@router.post("/name")
async def voice_name(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.name = (speech or "").strip()[:80]
    return gather("/voice/city", "Thanks. What city is the project located in?")

@router.post("/city")
async def voice_city(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.city = (speech or "").strip()[:60]
    return gather("/voice/type", "Is this interior painting, exterior, or both?")

@router.post("/type")
async def voice_type(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    s = norm(speech)
    if "both" in s:
        st.project_type = "both"
    elif "exterior" in s or "outside" in s:
        st.project_type = "exterior"
    elif "interior" in s or "inside" in s:
        st.project_type = "interior"
    else:
        return gather("/voice/type", "Just to confirm—interior, exterior, or both?")

    return gather("/voice/size", "About how many rooms, or roughly how many square feet?")

@router.post("/size")
async def voice_size(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.size = (speech or "").strip()[:80]
    return gather("/voice/timeline", "Are you looking to start soon, or just gathering estimates right now?")

@router.post("/timeline")
async def voice_timeline(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.timeline = (speech or "").strip()[:80]
    return gather("/voice/address", "Perfect. What’s the property address for the walkthrough?")

@router.post("/address")
async def voice_address(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.address = (speech or "").strip()[:140]
    return gather("/voice/email", "What’s the best email to send your estimate to? You can say it slowly.")

@router.post("/email")
async def voice_email(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.email = (speech or "").strip()[:140]

    now = datetime.now(tz=PACIFIC)
    slots = build_candidate_slots(now, business_days=10)[:2]
    st.offered_slots = [dt.isoformat() for dt in slots]

    if len(slots) < 2:
        vr = VoiceResponse()
        vr.say("Thanks. We’re fully booked during our weekday hours right now. Nathon will call you back to coordinate a time.")
        send_owner_sms(
            f"CALLBACK NEEDED (no slots)\\nName: {st.name}\\nCity: {st.city}\\nAddress: {st.address}\\nType: {st.project_type}\\nEmail: {st.email}"
        )
        clear_state(call_sid)
        return as_xml(vr)

    prompt = (
        "Great. We book walkthroughs Monday through Friday between 9 and 5. "
        f"I have {format_spoken(slots[0])}, or {format_spoken(slots[1])}. "
        "Which works better—first or second?"
    )
    return gather("/voice/schedule", prompt)

@router.post("/schedule")
async def voice_schedule(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    choice = pick_first_or_second(speech)
    if choice is None:
        return gather("/voice/schedule", "No problem—would you like the first option or the second option?")

    idx = 0 if choice == 1 else 1
    chosen = st.offered_slots[idx]
    dt = datetime.fromisoformat(chosen)

    vr = VoiceResponse()
    vr.say(f"Perfect. You’re scheduled for {format_spoken(dt)}. The walkthrough is free and takes about 20 to 30 minutes.")
    vr.say("If anything changes, just call us back. We’ll see you then. Bye!")

    send_owner_sms(
        "NEW WALKTHROUGH (VOICE)\\n"
        f"Name: {st.name}\\nCity: {st.city}\\nAddress: {st.address}\\n"
        f"Type: {st.project_type}\\nSize: {st.size}\\nTimeline: {st.timeline}\\n"
        f"When: {format_spoken(dt)}\\nEmail: {st.email}"
    )

    clear_state(call_sid)
    return as_xml(vr)
