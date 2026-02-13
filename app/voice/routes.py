from __future__ import annotations

import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather

from .state import get_state, clear_state
from .scheduling import build_candidate_slots, format_spoken, PACIFIC
from .notify import send_owner_sms
from app.google_calendar import is_free, create_event

router = APIRouter()


def as_xml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="text/xml")


def gather(action: str, prompt: str) -> Response:
    vr = VoiceResponse()
    g = Gather(
        input="speech",
        action=action,
        method="POST",
        speech_timeout="auto",
        language="en-US",
    )
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
    print("VOICE: root", {"CallSid": call_sid})

    return gather(
        "/voice/intent",
        "Hi, thanks for calling White’s Painting and Renovations here in Ukiah. "
        "This is Sally. Are you calling for a free estimate, a project update, or billing?",
    )


@router.post("/intent")
async def voice_intent(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    print("VOICE: intent", {"CallSid": call_sid, "SpeechResult": speech})

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
    print("VOICE: name", {"CallSid": call_sid, "name": st.name})
    return gather("/voice/city", "Thanks. What city is the project located in?")


@router.post("/city")
async def voice_city(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.city = (speech or "").strip()[:60]
    print("VOICE: city", {"CallSid": call_sid, "city": st.city})
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

    print("VOICE: type", {"CallSid": call_sid, "type": st.project_type})
    return gather("/voice/size", "About how many rooms, or roughly how many square feet?")


@router.post("/size")
async def voice_size(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.size = (speech or "").strip()[:80]
    print("VOICE: size", {"CallSid": call_sid, "size": st.size})
    return gather("/voice/timeline", "Are you looking to start soon, or just gathering estimates right now?")


@router.post("/timeline")
async def voice_timeline(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.timeline = (speech or "").strip()[:80]
    print("VOICE: timeline", {"CallSid": call_sid, "timeline": st.timeline})
    return gather("/voice/address", "Perfect. What’s the property address for the walkthrough?")


@router.post("/address")
async def voice_address(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.address = (speech or "").strip()[:140]
    print("VOICE: address", {"CallSid": call_sid, "address": st.address})
    return gather("/voice/email", "What’s the best email to send your estimate to? You can say it slowly.")


@router.post("/email")
async def voice_email(request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid", ""))
    speech = str(form.get("SpeechResult", ""))
    st = get_state(call_sid)

    st.email = (speech or "").strip()[:140]
    print("VOICE: email", {"CallSid": call_sid, "email": st.email})

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "natureme500@gmail.com")
    print("VOICE: calendar_id", calendar_id)

    now = datetime.now(tz=PACIFIC)
    candidates = build_candidate_slots(now, business_days=10)

    good: list[datetime] = []
    for start in candidates:
        end = start + timedelta(minutes=60)
        try:
            if is_free(calendar_id, start, end):
                good.append(start)
        except Exception as e:
            print("GCAL: freebusy FAILED", repr(e))
            # don’t break; still offer slots without freebusy if Google is flaky
            break

        if len(good) >= 2:
            break

    # If Google free/busy didn’t return slots, fall back to first two candidates
    if len(good) < 2:
        good = candidates[:2]

    slots = good
    st.offered_slots = [dt.isoformat() for dt in slots]
    print("VOICE: offered_slots", st.offered_slots)

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

    print("VOICE: schedule", {"CallSid": call_sid, "SpeechResult": speech, "offered": st.offered_slots})

    choice = pick_first_or_second(speech)
    if choice is None:
        return gather("/voice/schedule", "No problem—would you like the first option or the second option?")

    if not st.offered_slots or len(st.offered_slots) < 2:
        return gather("/voice/", "Something changed with scheduling. Let’s start over.")

    idx = 0 if choice == 1 else 1
    chosen = st.offered_slots[idx]
    dt = datetime.fromisoformat(chosen)

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "natureme500@gmail.com")
    start = dt
    end = dt + timedelta(minutes=60)

    summary = f"Estimate – {st.name} – {st.city}"
    description = (
        f"Email: {st.email}\n"
        f"Type: {st.project_type}\n"
        f"Size: {st.size}\n"
        f"Timeline: {st.timeline}\n"
    )

    try:
        ev = create_event(
            calendar_id=calendar_id,
            start=start,
            end=end,
            summary=summary,
            location=st.address or "",
            description=description,
        )
        print("GCAL: created event", ev.get("id"))
    except Exception as e:
        print("GCAL: create_event FAILED", repr(e))
        send_owner_sms(f"CALENDAR BOOKING FAILED\n{e}\nLead: {st.name} | {st.city} | {st.address}")

    vr = VoiceResponse()
    vr.say(f"Perfect. You’re scheduled for {format_spoken(dt)}. The walkthrough is free and takes about 20 to 30 minutes.")
    vr.say("If anything changes, just call us back. We’ll see you then. Bye!")

    send_owner_sms(
        "NEW WALKTHROUGH (VOICE)\n"
        f"Name: {st.name}\nCity: {st.city}\nAddress: {st.address}\n"
        f"Type: {st.project_type}\nSize: {st.size}\nTimeline: {st.timeline}\n"
        f"When: {format_spoken(dt)}\nEmail: {st.email}"
    )

    clear_state(call_sid)
    return as_xml(vr)
