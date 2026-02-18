from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

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
# WEB LEAD SUBMISSION
# =========================
@app.post("/web/lead")
async def web_lead(payload: dict):
    return JSONResponse({"ok": True, "received": payload})


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
