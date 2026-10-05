import os
import sqlite3
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

DB_FILE = "licenses.db"
ADMIN_KEY = os.getenv("ADMIN_KEY")


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            chat_id TEXT PRIMARY KEY,
            expires_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    return conn


class LicenseRequest(BaseModel):
    chat_id: str


class AdminRequest(BaseModel):
    chat_id: str
    days: int


@app.get("/")
def home():
    return {"status": "online"}


@app.post("/check")
def check_license(req: LicenseRequest):
    conn = db()
    row = conn.execute(
        "SELECT expires_at, active FROM licenses WHERE chat_id = ?",
        (req.chat_id.strip(),)
    ).fetchone()
    conn.close()

    if not row:
        return {"status": "denied", "message": "License not found"}

    expires_at, active = row

    if not active:
        return {"status": "denied", "message": "License revoked"}

    expiry = datetime.fromisoformat(expires_at)
    now = datetime.now(timezone.utc)

    if now >= expiry:
        return {
            "status": "denied",
            "message": "License expired",
            "expires_at": expires_at
        }

    return {
        "status": "ok",
        "expires_at": expires_at
    }


def verify_admin(key):
    if not ADMIN_KEY or key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Admin access denied")


@app.post("/admin/add")
def add_license(
    req: AdminRequest,
    x_admin_key: str = Header(default="")
):
    verify_admin(x_admin_key)

    if req.days <= 0:
        raise HTTPException(status_code=400, detail="Days must be greater than 0")

    expiry = datetime.now(timezone.utc) + timedelta(days=req.days)

    conn = db()
    conn.execute(
        """
        INSERT OR REPLACE INTO licenses
        (chat_id, expires_at, active)
        VALUES (?, ?, 1)
        """,
        (req.chat_id.strip(), expiry.isoformat())
    )
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "chat_id": req.chat_id.strip(),
        "expires_at": expiry.isoformat()
    }


@app.post("/admin/extend")
def extend_license(
    req: AdminRequest,
    x_admin_key: str = Header(default="")
):
    verify_admin(x_admin_key)

    conn = db()
    row = conn.execute(
        "SELECT expires_at FROM licenses WHERE chat_id = ?",
        (req.chat_id.strip(),)
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="License not found")

    current_expiry = datetime.fromisoformat(row[0])
    now = datetime.now(timezone.utc)

    base = max(current_expiry, now)
    new_expiry = base + timedelta(days=req.days)

    conn.execute(
        "UPDATE licenses SET expires_at = ?, active = 1 WHERE chat_id = ?",
        (new_expiry.isoformat(), req.chat_id.strip())
    )
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "chat_id": req.chat_id.strip(),
        "expires_at": new_expiry.isoformat()
    }


@app.post("/admin/revoke")
def revoke_license(
    req: LicenseRequest,
    x_admin_key: str = Header(default="")
):
    verify_admin(x_admin_key)

    conn = db()
    conn.execute(
        "UPDATE licenses SET active = 0 WHERE chat_id = ?",
        (req.chat_id.strip(),)
    )
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "message": "License revoked"
    }
