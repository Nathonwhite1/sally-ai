from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Serve /static/* from app/static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.post("/web/lead")
async def web_lead(payload: dict):
    return JSONResponse({"ok": True, "received": payload})
from fastapi.responses import PlainTextResponse

@app.post("/sms", response_class=PlainTextResponse)
async def sms_webhook(
    From: str = Form(None),
    Body: str = Form(""),
):
    reply = "Hi! I’m Sally 👋 Thanks for texting. What city are you in and is this interior, exterior, or cabinets?"
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply}</Message></Response>'
