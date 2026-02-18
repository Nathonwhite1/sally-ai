import os
import requests

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# =========================
# ENV
# =========================
GHL_WEBHOOK_URL = (os.getenv("GHL_WEBHOOK_URL") or "").strip()


# =========================
# DEBUG
# =========================
@app.get("/__debug_env", response_class=JSONResponse)
async def __debug_env():
    v = (os.getenv("GHL_WEBHOOK_URL") or "").strip()
    return {
        "has_GHL_WEBHOOK_URL": bool(v),
        "GHL_WEBHOOK_URL_preview": (v[:80] + "...") if len(v) > 80 else v
    }


@app.get("/__routes", response_class=JSONResponse)
async def __routes():
    return {"routes": sorted([getattr(r, "path", "") for r in app.routes])}


# =========================
# STATIC + TEMPLATES
# =========================
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# =========================
# PAGES
# =========================
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy-policy.html", {"request": request})


@app.get("/privacy-policy.html", response_class=HTMLResponse)
async def privacy_policy_html(request: Request):
    return templates.TemplateResponse("privacy-policy.html", {"request": request})


@app.get("/terms-and-conditions", response_class=HTMLResponse)
async def terms_and_conditions(request: Request):
    return templates.TemplateResponse("terms-and-conditions.html", {"request": request})


@app.get("/terms-and-conditions.html", response_class=HTMLResponse)
async def terms_and_conditions_html(request: Request):
    return templates.TemplateResponse("terms-and-conditions.html", {"request": request})


# =========================
# WEB LEAD SUBMISSION (FORWARD TO HIGHLEVEL INBOUND WEBHOOK)
# IMPORTANT: includes optional email fallback so HL can create contact even if phone mapping glitches
# =========================
@app.post("/web/lead")
async def web_lead(payload: dict):
    ghl_url = (os.getenv("GHL_WEBHOOK_URL") or "").strip()
    if not ghl_url:
        raise HTTPException(status_code=500, detail="GHL_WEBHOOK_URL is not set in Render env vars.")

    # Pull + normalize fields
    first_name = (payload.get("first_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip()  # optional but helps HL differentiation
    project_type = (payload.get("project_type") or "").strip()
    address = (payload.get("address") or "").strip()
    city = (payload.get("city") or "").strip()
    notes = (payload.get("notes") or "").strip()
    sms_consent = bool(payload.get("sms_consent"))

    # Website required fields (keep your existing requirements)
    if not project_type or not address or not city:
        raise HTTPException(status_code=400, detail="Missing required fields: project_type, address, city")

    # HighLevel differentiation requirement (needs at least one of email or phone)
    if not phone and not email:
        raise HTTPException(status_code=400, detail="Missing required field: phone or email")

    webhook_payload = {
        "source": "website",
        "first_name": first_name,
        "phone": phone,
        "email": email,
        "project_type": project_type,
        "address": address,
        "city": city,
        "notes": notes,
        "sms_consent": sms_consent,
    }

    try:
        r = requests.post(ghl_url, json=webhook_payload, timeout=20)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forwarding failed: {type(e).__name__}: {e}")

    if not (200 <= r.status_code < 300):
        raise HTTPException(status_code=502, detail=f"HighLevel returned {r.status_code}: {r.text[:300]}")

    return JSONResponse({"ok": True, "forward_status": r.status_code})


# =========================
# SMS WEBHOOK (Twilio)
# =========================
@app.post("/sms", response_class=PlainTextResponse)
async def sms_webhook(
    From: str = Form(None),
    Body: str = Form(""),
):
    reply = (
        "Hi! I’m Sally 👋 Thanks for texting. "
        "What city are you in and is this interior, exterior, or cabinets?"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{reply}</Message></Response>"
    )


# =========================
# VOICE ROUTES
# =========================
from app.voice.routes import router as voice_router
app.include_router(voice_router, prefix="/voice")
