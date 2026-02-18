import os
import requests

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# HighLevel Inbound Webhook URL (set in Render env vars)
GHL_WEBHOOK_URL = os.getenv("GHL_WEBHOOK_URL", "").strip()

# Debug: list all routes currently registered (useful for Render)
@app.get("/__routes", response_class=JSONResponse)
async def __routes():
    return {"routes": sorted([getattr(r, "path", "") for r in app.routes])}

# Serve /static/* from app/static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


# =========================
# PAGES
# =========================
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


# Privacy Policy (support both /privacy-policy and /privacy-policy.html)
@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy-policy.html", {"request": request})

@app.get("/privacy-policy.html", response_class=HTMLResponse)
async def privacy_policy_html(request: Request):
    return templates.TemplateResponse("privacy-policy.html", {"request": request})


# Terms (support both /terms-and-conditions and /terms-and-conditions.html)
@app.get("/terms-and-conditions", response_class=HTMLResponse)
async def terms_and_conditions(request: Request):
    return templates.TemplateResponse("terms-and-conditions.html", {"request": request})

@app.get("/terms-and-conditions.html", response_class=HTMLResponse)
async def terms_and_conditions_html(request: Request):
    return templates.TemplateResponse("terms-and-conditions.html", {"request": request})


# =========================
# WEB LEAD SUBMISSION (FORWARD TO HIGHLEVEL INBOUND WEBHOOK)
# =========================
@app.post("/web/lead")
async def web_lead(payload: dict):
    """
    Expects JSON like:
    {
      "first_name": "Maria",
      "phone": "(707) 555-1234",
      "project_type": "Interior Painting",
      "address": "123 Main St",
      "city": "Ukiah",
      "notes": "…",
      "sms_consent": true/false
    }
    """
    if not GHL_WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="Missing GHL_WEBHOOK_URL (set it in Render env vars).")

    first_name = (payload.get("first_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    project_type = (payload.get("project_type") or "").strip()
    address = (payload.get("address") or "").strip()
    city = (payload.get("city") or "").strip()
    notes = (payload.get("notes") or "").strip()
    sms_consent = bool(payload.get("sms_consent"))

    # Match your front-end required fields
    if not phone or not project_type or not address or not city:
        raise HTTPException(status_code=400, detail="Missing required fields")

    webhook_payload = {
        "source": "website",
        "first_name": first_name,
        "phone": phone,
        "project_type": project_type,
        "address": address,
        "city": city,
        "notes": notes,
        "sms_consent": sms_consent,
        "tags": [
            "Website Lead",
            f"Project: {project_type}" if project_type else "Project: Unknown",
            "SMS Opt-In" if sms_consent else "NO SMS CONSENT",
        ],
    }

    try:
        r = requests.post(GHL_WEBHOOK_URL, json=webhook_payload, timeout=20)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"HighLevel webhook forward failed: {e}")

    if not (200 <= r.status_code < 300):
        raise HTTPException(status_code=502, detail=f"HighLevel webhook error {r.status_code}: {r.text}")

    # Return success to the browser either way
    return JSONResponse({"ok": True})


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
