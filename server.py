from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timezone

app = FastAPI()

# Chat ID : Expiry date
LICENSES = {
    "123456789": "2026-10-08T23:59:59+00:00",
}


class LicenseRequest(BaseModel):
    chat_id: str


@app.get("/")
def home():
    return {"status": "online"}


@app.post("/check")
def check_license(req: LicenseRequest):
    chat_id = str(req.chat_id).strip()

    expiry = LICENSES.get(chat_id)

    if not expiry:
        return {
            "status": "denied",
            "message": "License not found"
        }

    try:
        expires_at = datetime.fromisoformat(expiry)
    except ValueError:
        return {
            "status": "denied",
            "message": "Invalid expiry date"
        }

    now = datetime.now(timezone.utc)

    if now >= expires_at:
        return {
            "status": "denied",
            "message": "License expired",
            "expires_at": expiry
        }

    return {
        "status": "ok",
        "expires_at": expiry
    }
