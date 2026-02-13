import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

PACIFIC = ZoneInfo("America/Los_Angeles")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _svc():
    # Production (Render): store the entire JSON in an env var
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
print("GCAL ENV CHECK → has_json:", bool(sa_json), "calendar_id:", os.getenv("GOOGLE_CALENDAR_ID"))


    # Local dev fallback: read from file
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "google_credentials.json").strip()

    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)

    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def is_free(calendar_id: str, start: datetime, end: datetime) -> bool:
    service = _svc()
    body = {
        "timeMin": start.astimezone(PACIFIC).isoformat(),
        "timeMax": end.astimezone(PACIFIC).isoformat(),
        "timeZone": "America/Los_Angeles",
        "items": [{"id": calendar_id}],
    }
    resp = service.freebusy().query(body=body).execute()
    busy = resp["calendars"][calendar_id].get("busy", [])
    return len(busy) == 0

def create_event(calendar_id: str, start: datetime, end: datetime, summary: str, location: str, description: str):
    service = _svc()
    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start.astimezone(PACIFIC).isoformat(), "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": end.astimezone(PACIFIC).isoformat(), "timeZone": "America/Los_Angeles"},
    }
    return service.events().insert(calendarId=calendar_id, body=event).execute()
