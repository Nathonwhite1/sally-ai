import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

from .models import Lead, Customer, Message, Proposal

WARRANTY_LINE = "All workmanship is covered by a 6-month warranty from date of completion."
FINANCING_LINE = "Financing available to qualified customers."

def generate_proposal_and_pdf(db: Session, lead: Lead) -> Proposal:
    customer = db.get(Customer, lead.customer_id)

    total_price = price_placeholder(lead)
    scope_text, extras_text = build_scope_and_extras(db, lead)

    payment_text = (
        ",000 Deposit to Schedule\\n"
        "10% Due at scheduling (deposit applied)\\n"
        "30% Mid-project progress payment\\n"
        "60% Final payment upon completion / final walkthrough"
    )

    proposal = Proposal(
        lead_id=lead.id,
        total_price=total_price,
        scope_text=scope_text,
        extras_text=extras_text,
        payment_text=payment_text,
        warranty_text=WARRANTY_LINE,
        pdf_path=None,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    out_dir = os.path.join(os.getcwd(), "proposals")
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"proposal-{proposal.id}.pdf")

    render_pdf(pdf_path, customer, lead, proposal)
    proposal.pdf_path = pdf_path
    db.commit()
    return proposal

def price_placeholder(lead: Lead) -> int:
    base = {
        "interior": 3500,
        "exterior": 5500,
        "cabinets": 4500,
        "flooring": 6000,
        "remodel": 8000
    }.get(lead.project_type or "", 3500)

    notes = str(lead.intake_data or {}).lower()
    if "heavy" in notes and ("patch" in notes or "prep" in notes):
        base += 750
    return base

def build_scope_and_extras(db: Session, lead: Lead) -> tuple[str, str]:
    msgs = db.scalars(
        select(Message)
        .where(Message.lead_id == lead.id, Message.direction == "in")
        .order_by(desc(Message.created_at))
        .limit(10)
    ).all()
    notes = "\\n".join([f"- {m.body}" for m in reversed(msgs)])

    scope = (
        "BASE SCOPE (Included)\\n"
        "- Surface preparation as needed (protect floors/furnishings, sanding, patching, caulking)\\n"
        "- Prime where required\\n"
        "- Two finish coats unless otherwise specified\\n"
        "- Daily cleanup and final walkthrough\\n\\n"
        "PROJECT NOTES (from intake)\\n"
        f"{notes if notes else '- (none)'}"
    )

    extras = (
        "EXTRAS / MATERIALS TBD (Not Included in Base Price)\\n"
        "- Repairs beyond normal patching (rotted wood replacement, structural repairs)\\n"
        "- Owner-selected specialty materials not yet chosen (fixtures, hardware, tile, appliances)\\n"
        "- Unforeseen damage found after work begins (requires change order approval)\\n"
    )
    return scope, extras

def render_pdf(path: str, customer: Customer, lead: Lead, proposal: Proposal):
    c = canvas.Canvas(path, pagesize=LETTER)
    width, height = LETTER

    y = height - 1 * inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1 * inch, y, "White’s Painting & Renovations")
    y -= 0.25 * inch

    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, y, f"Proposal #{proposal.id}  •  Date: {datetime.now().strftime('%Y-%m-%d')}")
    y -= 0.2 * inch

    email = (customer.email or (lead.intake_data or {}).get("email", "") or "")
    c.drawString(1 * inch, y, f"Client Phone: {customer.phone}  Email: {email}"[:110])
    y -= 0.2 * inch

    addr = lead.address or (lead.intake_data or {}).get("address_raw", "")
    city = lead.city or (lead.intake_data or {}).get("city_guess", "")
    c.drawString(1 * inch, y, f"Property: {addr} {city}"[:110])
    y -= 0.35 * inch

    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, y, "Total Investment (Flat Rate)")
    y -= 0.25 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, y, f"")
    y -= 0.35 * inch

    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, y, FINANCING_LINE)
    y -= 0.25 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawString(1 * inch, y, "Payment Schedule")
    y -= 0.2 * inch
    c.setFont("Helvetica", 10)
    for line in proposal.payment_text.splitlines():
        c.drawString(1.1 * inch, y, line)
        y -= 0.18 * inch

    y -= 0.15 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1 * inch, y, "Scope of Work")
    y -= 0.2 * inch
    y = draw_multiline(c, 1 * inch, y, proposal.scope_text)

    y -= 0.15 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1 * inch, y, "Extras / Materials TBD")
    y -= 0.2 * inch
    y = draw_multiline(c, 1 * inch, y, proposal.extras_text)

    y -= 0.15 * inch
    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, y, proposal.warranty_text)

    c.showPage()
    c.save()

def draw_multiline(c, x, y, text, max_lines=200):
    c.setFont("Helvetica", 10)
    for i, line in enumerate(text.splitlines()):
        if i > max_lines or y < 1 * inch:
            c.showPage()
            y = 10.5 * inch
            c.setFont("Helvetica", 10)
        c.drawString(x, y, line[:120])
        y -= 0.18 * inch
    return y
