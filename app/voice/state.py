from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class LeadState:
    step: str = "intent"
    intent: Optional[str] = None

    name: Optional[str] = None
    city: Optional[str] = None
    project_type: Optional[str] = None
    size: Optional[str] = None
    timeline: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None

    offered_slots: list[str] = field(default_factory=list)
    chosen_slot: Optional[str] = None

CALL_STATE: Dict[str, LeadState] = {}

def get_state(call_sid: str) -> LeadState:
    if call_sid not in CALL_STATE:
        CALL_STATE[call_sid] = LeadState()
    return CALL_STATE[call_sid]

def clear_state(call_sid: str) -> None:
    CALL_STATE.pop(call_sid, None)
