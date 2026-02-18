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
    ghl_url = (os.getenv("GHL_WEBHOOK_URL") or "").strip()
    if not ghl_url:
        raise HTTPException(status_code=500, detail="GHL_WEBHOOK_URL is not set in Render env vars.")

    webhook_payload = {
        "first_name": (payload.get("first_name") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "project_type": (payload.get("project_type") or "").strip(),
        "address": (payload.get("address") or "").strip(),
        "city": (payload.get("city") or "").strip(),
        "notes": (payload.get("notes") or "").strip(),
        "sms_consent": bool(payload.get("sms_consent")),
        "source": "website",
    }

    # required fields
    if not webhook_payload["phone"] or not webhook_payload["project_type"] or not webhook_payload["address"] or not webhook_payload["city"]:
        raise HTTPException(status_code=400, detail="Missing required fields: phone, project_type, address, city")

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
