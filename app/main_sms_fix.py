@app.post("/sms", response_class=PlainTextResponse)
async def sms_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db),
):
    phone = From.strip()
    body = (Body or "").strip()

    customer = db.scalar(select(Customer).where(Customer.phone == phone))
    if not customer:
        customer = Customer(phone=phone, name=None, email=None)
        db.add(customer)
        db.commit()
        db.refresh(customer)

    lead = db.scalar(
        select(Lead)
        .where(Lead.customer_id == customer.id, Lead.status.in_(["new", "in_progress"]))
        .order_by(desc(Lead.created_at))
    )
    if not lead:
        lead = Lead(
            customer_id=customer.id,
            status="new",
            project_type=None,
            address=None,
            city=None,
            timeline=None,
            occupied=None,
            access_notes=None,
            intake_stage="stage1",
            intake_data={},
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
  <Message>{reply}</Message>
</Response>"""

    return PlainTextResponse(twiml, media_type="application/xml")
