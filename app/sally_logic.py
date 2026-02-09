import re
from sqlalchemy.orm import Session
from .models import Lead

SALLY_OPEN = (
    "Hi! This is Sally with White’s Painting & Renovations. "
    "Are you looking for interior painting, exterior painting, cabinets, or flooring/remodeling? "
    "And what’s the project address (city)?"
)

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def extract_email(text: str) -> str | None:
    m = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text, flags=re.I)
    return m.group(1) if m else None

def scope_questions(project_type: str | None) -> str:
    if project_type == "interior":
        return (
            "Quick questions so we quote it correctly:\\n"
            "1) Which rooms and ceiling height (8/9/vaulted)?\\n"
            "2) Walls only or walls + ceilings + trim/doors?\\n"
            "3) Any heavy patching, stains, smoke, or peeling paint?"
        )
    if project_type == "exterior":
        return (
            "Quick questions for exterior:\\n"
            "1) Full exterior or trim only?\\n"
            "2) One story or two?\\n"
            "3) Any peeling/bare wood or heavy prep spots?"
        )
    if project_type == "cabinets":
        return (
            "For cabinets:\\n"
            "1) About how many doors and drawers?\\n"
            "2) Painted or stained currently?\\n"
            "3) Do you want the inside boxes painted too?"
        )
    if project_type == "flooring":
        return (
            "For flooring:\\n"
            "1) Which rooms and approx square footage?\\n"
            "2) Remove old flooring + haul away?\\n"
            "3) Baseboards included and is furniture moving needed?"
        )
    if project_type == "remodel":
        return (
            "For remodels:\\n"
            "1) Which areas (bath/kitchen/etc.)?\\n"
            "2) Any demo involved?\\n"
            "3) Are fixtures/materials selected or TBD?"
        )
    return "Tell me a little about what you want done and the address (city), and I’ll guide you from there."

def sally_next_message_and_update_state(db: Session, lead: Lead, inbound: str) -> str:
    t = normalize(inbound)
    stage = lead.intake_stage or "stage1"
    data = lead.intake_data or {}

    if stage == "stage1":
        # Detect project type
        if any(k in t for k in ["interior", "inside", "bedroom", "living", "walls", "ceiling"]):
            lead.project_type = "interior"
        elif any(k in t for k in ["exterior", "outside", "trim", "siding", "fascia", "stucco"]):
            lead.project_type = "exterior"
        elif any(k in t for k in ["cabinet", "cabinets"]):
            lead.project_type = "cabinets"
        elif any(k in t for k in ["floor", "flooring", "lvp", "laminate", "carpet"]):
            lead.project_type = "flooring"
        elif any(k in t for k in ["remodel", "bath", "bathroom", "shower", "tile"]):
            lead.project_type = "remodel"

        # Capture address/city if present
        if len(inbound.strip()) >= 6 and any(ch.isdigit() for ch in inbound):
            data["address_raw"] = inbound.strip()
        elif len(inbound.strip()) >= 3 and "city_guess" not in data:
            data["city_guess"] = inbound.strip()

        lead.intake_data = data

        if not lead.project_type:
            lead.intake_stage = "stage1"
            db.commit()
            return (
                "Got it. Is this for interior painting, exterior painting, cabinets, or flooring/remodeling? "
                "And what’s the project address (city)?"
            )

        if "address_raw" not in data and not lead.address:
            lead.intake_stage = "stage_address"
            lead.status = "in_progress"
            db.commit()
            return "Thanks — what’s the property address (or nearest cross streets + city)?"

        lead.intake_stage = "stage_core"
        lead.status = "in_progress"
        db.commit()
        return "Perfect. What timeline are you hoping for (ASAP, this month, next month), and is the home occupied or vacant?"

    if stage == "stage_address":
        data["address_raw"] = inbound.strip()
        lead.intake_data = data
        lead.intake_stage = "stage_core"
        lead.status = "in_progress"
        db.commit()
        return "Great — what timeline are you hoping for, and is the home occupied or vacant?"

    if stage == "stage_core":
        if "timeline" not in data:
            data["timeline"] = inbound.strip()
            lead.timeline = inbound.strip()

        if "occupied" not in data:
            if "vacant" in t or "empty" in t:
                data["occupied"] = False
                lead.occupied = False
            elif "occupied" in t or "we live" in t or "living" in t:
                data["occupied"] = True
                lead.occupied = True

        lead.intake_data = data
        lead.intake_stage = "stage_scope"
        db.commit()
        return scope_questions(lead.project_type)

    if stage == "stage_scope":
        data.setdefault("scope_notes", [])
        data["scope_notes"].append(inbound.strip())
        lead.intake_data = data
        lead.intake_stage = "stage_logistics"
        db.commit()
        return (
            "If it’s easy, can you text 3–6 photos (wide shots + any problem areas like peeling/patches)? "
            "Also, what’s the best email to send your written proposal to after the walkthrough?"
        )

    if stage == "stage_logistics":
        email = extract_email(inbound)
        if email:
            data["email"] = email
        else:
            data.setdefault("logistics_notes", [])
            data["logistics_notes"].append(inbound.strip())

        lead.intake_data = data
        db.commit()
        return (
            "Awesome. We offer free estimates. What day works best this week or next week for a quick walkthrough?"
        )

    db.commit()
    return SALLY_OPEN
