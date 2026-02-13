import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build

PACIFIC = ZoneInfo("America/Los_Angeles")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _svc():
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "google_credentials.json").strip()
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def is_free(calendar_id: str, start: datetime, end: datetime) -> bool:
    service = _svc()
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
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
        "start": {"dateTime": start.isoformat(), "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": end.isoformat(), "timeZone": "America/Los_Angeles"},
    }
    return service.events().insert(calendarId=calendar_id, body=event).execute()
