from __future__ import annotations
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import List

PACIFIC = ZoneInfo("America/Los_Angeles")

WORK_START = time(9, 0)
WORK_END = time(17, 0)

APPT_MINUTES = 30
BUFFER_MINUTES = 30
BLOCK_MINUTES = APPT_MINUTES + BUFFER_MINUTES

# Clean grid that respects buffer and keeps your day sane
GRID_TIMES = [
    time(9, 0),
    time(10, 30),
    time(12, 0),
    time(13, 30),
    time(15, 0),
    time(16, 0),
]

def is_weekday(dt: datetime) -> bool:
    return dt.weekday() < 5

def build_candidate_slots(now: datetime, business_days: int = 10) -> List[datetime]:
    now = now.astimezone(PACIFIC)
    candidates: List[datetime] = []
    day = now
    added = 0

    while added < business_days:
        if is_weekday(day):
            for t in GRID_TIMES:
                start = datetime.combine(day.date(), t, tzinfo=PACIFIC)
                if start <= now + timedelta(minutes=10):
                    continue
                end = start + timedelta(minutes=BLOCK_MINUTES)
                if start.time() < WORK_START:
                    continue
                if end.time() > WORK_END:
                    continue
                candidates.append(start)
            added += 1
        day = day + timedelta(days=1)

    return candidates

def format_spoken(dt: datetime) -> str:
    dt = dt.astimezone(PACIFIC)
    return f"{dt.strftime('%A')} at {dt.strftime('%I:%M %p').lstrip('0')}"
