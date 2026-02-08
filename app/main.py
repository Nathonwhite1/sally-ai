from fastapi import FastAPI, Request, Form, Depends, HTTPException, Body
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
import re
import os

DATABASE_URL = "sqlite:///./sally.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

app = FastAPI(title="Sally AI", version="0.1.0")

templates = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"])
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    status = Column(String, default="new")
    project_type = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    timeline = Column(String, nullable=True)
    occupied = Column(String, nullable=True)
    access_notes = Column(String, nullable=True)
    intake_stage = Column(String, default="stage1")
    intake_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    direction = Column(String)
    body = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

ADMIN_PASSWORD = "mysupersecret"

def require_admin(pw: str | None):
    if pw != ADMIN_PASSWORD:
        raise HTTPException(403, "Unauthorized")

def escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )

def sally_next_message_and_update_state(db: Session, lead: Lead, incoming: str) -> str:

    stage = lead.intake_stage

    if stage == "stage1":
        lead.project_type = incoming
        lead.intake_stage = "stage2"
        db.commit()
        return "Great! What is the property address?"

    if stage == "stage2":
        lead.address = incoming
        lead.intake_stage = "stage3"
        db.commit()
        return "Thanks! What city is the project in?"

    if stage == "stage3":
        lead.city = incoming
        lead.intake_stage = "stage4"
        db.commit()
        return "Is the property currently occupied? (Yes or No)"

    if stage == "stage4":
        lead.occupied = incoming
        lead.intake_stage = "stage5"
        db.commit()
        return "What timeline are you hoping for?"

    if stage == "stage5":
        lead.timeline = incoming
        lead.intake_stage = "complete"
        db.commit()
        return "Awesome. We offer free estimates. What day works best this week or next week for a quick walkthrough?"

    return "Thanks! We’ll be in touch shortly."

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    template = templates.get_template("landing.html")
    return HTMLResponse(template.render(request=request))

@app.post("/sms", response_class=PlainTextResponse)
async def sms_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db),
):

    phone = From.strip()
    body = (Body or "").strip()

    customer = db.query(Customer).filter(Customer.phone == phone).first()
    if not customer:
        customer = Customer(phone=phone)
        db.add(customer)
        db.commit()
        db.refresh(customer)

    lead = db.query(Lead).filter(
        Lead.customer_id == customer.id,
        Lead.status.in_(["new", "in_progress"])
    ).order_by(desc(Lead.created_at)).first()

    if not lead:
        lead = Lead(
            customer_id=customer.id,
            status="new",
            intake_stage="stage1"
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

    db.add(Message(lead_id=lead.id, direction="in", body=body))
    db.commit()

    reply = sally_next_message_and_update_state(db, lead, body)

    db.add(Message(lead_id=lead.id, direction="out", body=reply))
    db.commit()

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>{escape_xml(reply)}</Message>
</Response>"""

    return PlainTextResponse(twiml, media_type="application/xml")

@app.post("/web/lead")
def web_lead(payload: dict = Body(...), db: Session = Depends(get_db)):

    phone = (payload.get("phone") or "").strip()
    address = (payload.get("address") or "").strip()
    city = (payload.get("city") or "").strip()
    project_type = (payload.get("project_type") or "").strip()
    notes = (payload.get("notes") or "").strip()
    first_name = (payload.get("first_name") or "").strip()

    if not phone or not address or not city or not project_type:
        return JSONResponse({"ok": False, "error": "Missing required fields."}, status_code=400)

    customer = db.query(Customer).filter(Customer.phone == phone).first()

    if not customer:
        customer = Customer(phone=phone, name=first_name)
        db.add(customer)
        db.commit()
        db.refresh(customer)

    lead = Lead(
        customer_id=customer.id,
        project_type=project_type,
        address=address,
        city=city,
        status="new",
        intake_stage="complete",
        intake_data=notes
    )

    db.add(lead)
    db.commit()

    return {"ok": True, "lead_id": lead.id}

@app.get("/admin/leads", response_class=HTMLResponse)
def admin_leads(request: Request, pw: str | None = None, db: Session = Depends(get_db)):
    require_admin(pw)
    leads = db.query(Lead).order_by(desc(Lead.created_at)).all()
    template = templates.get_template("leads.html")
    return HTMLResponse(template.render(request=request, leads=leads, pw=pw))

@app.get("/admin/leads/{lead_id}", response_class=HTMLResponse)
def admin_lead_detail(request: Request, lead_id: int, pw: str | None = None, db: Session = Depends(get_db)):
    require_admin(pw)

    lead = db.query(Lead).get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")

    messages = db.query(Message).filter(Message.lead_id == lead_id).all()
    customer = db.query(Customer).get(lead.customer_id)

    template = templates.get_template("lead_detail.html")

    return HTMLResponse(template.render(
        request=request,
        lead=lead,
        customer=customer,
        messages=messages,
        pw=pw
    ))
