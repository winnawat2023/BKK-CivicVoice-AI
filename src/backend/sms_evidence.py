"""SMS and evidence relay for the API Guide's Voicebot confirmation flow."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator

PROVIDER_URL = "https://api-v2.thaibulksms.com/sms"
SMSKUB_URL = "https://console.sms-kub.com/api/messages"
LIVE_MODES = {"thaibulksms", "smskub"}
TICKET = re.compile(r"BKK-[0-9]{4,8}-[0-9]{4,8}")
MOBILE = re.compile(r"(?:0|\+?66)([689][0-9]{8})")
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
MIME_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_PHOTO = 5 * 1024 * 1024
DAY = 86400


def origin(value):
    url = urlsplit(value.strip())
    if url.scheme not in {"https", "http"} or not url.netloc or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
        raise ValueError("Voicebot and public URL must be HTTP(S) origins")
    return f"{url.scheme}://{url.netloc}"


def phone_number(value):
    match = MOBILE.fullmatch(value.strip().replace(" ", "").replace("-", ""))
    if not match:
        raise ValueError("Invalid Thai mobile number")
    return "+66" + match.group(1)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def ticket_sms(ticket, link):
    def compact(value, limit):
        if not isinstance(value, str):
            return ""
        value = re.sub(r"(?:https?://|www\.)\S+", "", value, flags=re.IGNORECASE)
        value = " ".join(value.split())
        return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"

    lines = ticket.get("summary_lines")
    insight = compact(lines[0], 68) if isinstance(lines, list) and lines else ""
    if not insight:
        insight = compact(ticket.get("sub_category") or ticket.get("category"), 68)
    location = compact(ticket.get("location_detail"), 40)
    district = compact(ticket.get("district"), 24)
    if district and ("เขต" + district) not in location:
        location = " ".join(filter(None, (location, "เขต" + district)))
    return "\n".join(filter(None, (ticket["ticket_id"], insight, location, f"ส่งรูป/พิกัด/แผนที่: {link}")))


def send_via_provider(client, mode, key, secret, sender, number, message):
    if mode == "smskub":
        reply = client.post(SMSKUB_URL, headers={"key": key}, json={
            "to": [number.removeprefix("+")], "from": sender, "message": message,
        })
        if 400 <= reply.status_code < 500:
            return "rejected", None
        if reply.status_code != 200:
            return "unknown", None
        result = reply.json()
        if result.get("error") or (result.get("code") is not None and result["code"] != 200):
            return "rejected", None
        counts = result.get("data")
        if result.get("code") == 200 and isinstance(counts, dict):
            if counts.get("block") == 1:
                return "rejected", None
            if counts.get("total") == 1 and counts.get("send") == 1 and counts.get("block") == 0:
                return "accepted", None
        return "unknown", None

    reply = client.post(PROVIDER_URL, auth=(key, secret), data={
        "sender": sender, "msisdn": number, "message": message,
    })
    if reply.status_code == 201:
        rows = reply.json().get("phone_number_list") or []
        provider_id = next((row.get("message_id") for row in rows if row.get("message_id")), None)
        return ("accepted" if provider_id else "rejected"), provider_id
    return ("rejected" if 400 <= reply.status_code < 500 else "unknown"), None


class ReviewedLocation(BaseModel):
    district: str | None = Field(default=None, max_length=60)
    location_detail: str = Field(default="", max_length=240)


class Confirmation(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="th", pattern="^(th|en)$")
    interaction_id: str = Field(pattern=r"^WEB-[a-fA-F0-9-]{36}$")
    reviewed_location: ReviewedLocation | None = None


class SendSMS(BaseModel):
    phone: str = Field(min_length=9, max_length=24)


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class MapLink(BaseModel):
    map_url: str = Field(min_length=1, max_length=2048)

    @field_validator("map_url")
    @classmethod
    def validate_map_url(cls, value):
        value = value.strip()
        url = urlsplit(value)
        if (url.scheme != "https" or url.username or url.password or url.port is not None
                or any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value):
            raise ValueError("กรุณาใช้ลิงก์ HTTPS จากแอปแผนที่")
        host = url.hostname
        if host in {"maps.app.goo.gl", "maps.google.com", "maps.apple.com", "openstreetmap.org", "www.openstreetmap.org"}:
            return value
        if host in {"google.com", "www.google.com", "goo.gl"} and (url.path == "/maps" or url.path.startswith("/maps/")):
            return value
        raise ValueError("รองรับลิงก์ Google Maps, Apple Maps หรือ OpenStreetMap")


def create_app(env=None, transport=None):
    env = os.environ if env is None else env
    mode = env.get("SMS_MODE", "disabled").lower().strip()
    if mode not in LIVE_MODES | {"disabled", "mock"}:
        raise ValueError("SMS_MODE must be disabled, mock, thaibulksms or smskub")
    backend = origin(env.get("SMS_VOICEBOT_ORIGIN", "http://127.0.0.1:8000"))
    public = origin(env.get("SMS_PUBLIC_ORIGIN", "http://127.0.0.1:8765"))
    allowed_origins = {public}
    allowed_origins.update(origin(item) for item in env.get(
        "SMS_BROWSER_ORIGINS", "http://127.0.0.1:8765,http://localhost:8765").split(",") if item.strip())
    key = env.get(f"{mode.upper()}_API_KEY", "").strip()
    secret = env.get("THAIBULKSMS_API_SECRET", "").strip() if mode == "thaibulksms" else ""
    sender = env.get(f"{mode.upper()}_SENDER", "").strip()
    relay_secret = env.get("SMS_CONFIRM_SECRET", "").strip()
    admin_token = env.get("SMS_ADMIN_TOKEN", "").strip()
    allowed_numbers = {phone_number(item) for item in env.get("SMS_ALLOWED_RECIPIENTS", "").split(",") if item.strip()}
    if mode in LIVE_MODES and not (
        key and sender and allowed_numbers and relay_secret and public.startswith("https://")
        and urlsplit(public).hostname not in LOOPBACK
    ):
        raise ValueError("Live SMS needs API key, sender, allowed recipients, a public HTTPS origin and SMS_CONFIRM_SECRET")
    if mode == "thaibulksms" and not secret:
        raise ValueError("ThaiBulkSMS requires THAIBULKSMS_API_SECRET")
    daily_limit = max(1, min(100, int(env.get("SMS_DAILY_LIMIT", "20"))))
    phone_limit = max(1, min(daily_limit, int(env.get("SMS_PER_NUMBER_DAILY_LIMIT", "3"))))
    db_path = Path(env.get("SMS_DB_PATH", "").strip() or f"data/sms-evidence-{mode}.sqlite3")

    @contextmanager
    def database():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    with database() as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS sms_grant (
            grant_hash TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, expires INTEGER NOT NULL
          );
          CREATE TABLE IF NOT EXISTS sms_send (
            ticket_id TEXT PRIMARY KEY, evidence_hash TEXT UNIQUE NOT NULL,
            recipient_hash TEXT NOT NULL, state TEXT NOT NULL, created INTEGER NOT NULL,
            expires INTEGER NOT NULL, provider_id TEXT, latitude REAL, longitude REAL,
            accuracy REAL, photo BLOB, photo_type TEXT, updated INTEGER
          );
        """)
        db.execute("BEGIN IMMEDIATE")
        if "map_url" not in {column["name"] for column in db.execute("PRAGMA table_info(sms_send)")}:
            db.execute("ALTER TABLE sms_send ADD COLUMN map_url TEXT")

    app = FastAPI(title="CivicVoice SMS & Evidence relay")
    app.add_middleware(CORSMiddleware, allow_origins=list(allowed_origins),
                       allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def prevent_cache(request, call_next):
        answer = await call_next(request)
        answer.headers["Cache-Control"] = "no-store"
        answer.headers["X-Content-Type-Options"] = "nosniff"
        return answer

    def token_from(request):
        scheme, _, value = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", value):
            raise HTTPException(401, "ไม่มีสิทธิ์เข้าถึงลิงก์นี้")
        return value

    def evidence_row(db, request):
        row = db.execute(
            """SELECT ticket_id, state, expires, latitude, longitude, accuracy, map_url,
               photo IS NOT NULL AS has_photo, updated FROM sms_send WHERE evidence_hash=?""",
            (digest(token_from(request)),),
        ).fetchone()
        if row is None or row["expires"] < time.time() or row["state"] not in {"mock", "accepted", "unknown"}:
            raise HTTPException(404, "ลิงก์ไม่ถูกต้องหรือหมดอายุ")
        return dict(row)

    def admin_only(request):
        header = request.headers.get("authorization", "")
        if not admin_token or not hmac.compare_digest(header.encode(), ("Bearer " + admin_token).encode()):
            raise HTTPException(401, "ไม่มีสิทธิ์เข้าถึงข้อมูลเจ้าหน้าที่")

    def fetch_ticket(ticket_id):
        with httpx.Client(timeout=3, transport=transport) as client:
            response = client.get(backend + "/api/v1/tickets/" + ticket_id)
            response.raise_for_status()
            ticket = response.json()
        if not isinstance(ticket, dict) or ticket.get("ticket_id") != ticket_id:
            raise ValueError("Unexpected ticket response")
        return ticket

    def valid_grant(db, grant_hash, now):
        grant = db.execute("SELECT ticket_id FROM sms_grant WHERE grant_hash=? AND expires>=?",
                           (grant_hash, now)).fetchone()
        if not grant:
            raise HTTPException(401, "สิทธิ์ขอ SMS หมดอายุหรือไม่ถูกต้อง")
        ticket_id = grant["ticket_id"]
        if db.execute("SELECT 1 FROM sms_send WHERE ticket_id=?", (ticket_id,)).fetchone():
            raise HTTPException(409, "มีการขอ SMS สำหรับคำร้องนี้แล้ว กรุณาตรวจผลก่อนส่งใหม่")
        return ticket_id

    @app.get("/api/sms/health")
    def health():
        return {"ready": mode != "disabled", "mode": mode, "requires_gateway": mode in LIVE_MODES}

    @app.post("/api/sms/confirm")
    def confirm(body: Confirmation, request: Request):
        if mode == "disabled":
            raise HTTPException(503, "บริการส่ง SMS ยังไม่เปิดใช้งาน")
        incoming_origin = request.headers.get("origin")
        local_origin = incoming_origin in allowed_origins and urlsplit(incoming_origin).hostname in LOOPBACK
        local_request = local_origin and request.url.hostname in LOOPBACK
        header = request.headers.get("X-SMS-Confirm-Secret", "")
        trusted = bool(relay_secret) and hmac.compare_digest(header.encode(), relay_secret.encode())
        if not (trusted or (mode == "mock" and local_request)):
            raise HTTPException(403, "ต้องยืนยันตัวตนผ่าน gateway ก่อนสร้างคำร้อง")
        try:
            with httpx.Client(timeout=35, transport=transport) as client:
                reply = client.post(backend + "/api/v1/voicebot/converse", json=body.model_dump(exclude_none=True))
            if reply.status_code in {400, 401, 403, 404, 409, 422}:
                raise HTTPException(reply.status_code, "Backend ไม่รับคำขอยืนยันคำร้อง")
            reply.raise_for_status()
            result = reply.json()
            if not isinstance(result, dict):
                raise ValueError("Expected object")
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, "ยังยืนยันผลจาก Voicebot ไม่ได้") from None
        ticket_id = result.get("ticket_id")
        result.pop("sms_grant", None)
        if result.get("success") is True and isinstance(ticket_id, str) and TICKET.fullmatch(ticket_id):
            grant = secrets.token_urlsafe(24)
            now = int(time.time())
            with database() as db:
                db.execute("DELETE FROM sms_grant WHERE expires < ?", (now,))
                db.execute("INSERT INTO sms_grant VALUES (?,?,?)", (digest(grant), ticket_id, now + 1800))
            result["sms_grant"] = grant
        return result

    @app.post("/api/sms/send")
    def send(body: SendSMS, request: Request):
        if mode == "disabled":
            raise HTTPException(503, "บริการส่ง SMS ยังไม่เปิดใช้งาน")
        try:
            number = phone_number(body.phone)
        except ValueError:
            raise HTTPException(422, "กรุณาใส่เบอร์มือถือไทยให้ถูกต้อง") from None
        if allowed_numbers and number not in allowed_numbers:
            raise HTTPException(403, "เบอร์นี้ยังไม่อยู่ในรายการทดสอบ")
        grant_hash = digest(token_from(request))
        evidence_token = secrets.token_urlsafe(24)
        hash_key = secret or (relay_secret if mode == "smskub" else "mock-only")
        recipient = hmac.new(hash_key.encode(), number.encode(), "sha256").hexdigest()
        with database() as db:
            ticket_id = valid_grant(db, grant_hash, int(time.time()))
        try:
            ticket = fetch_ticket(ticket_id)
        except (httpx.HTTPError, ValueError):
            raise HTTPException(424, "ยังอ่านคำร้องเพื่อจัดทำข้อความไม่ได้ กรุณาลองอีกครั้ง") from None
        link = f"{public}/tracking/?mode=evidence#token={evidence_token}"
        message = ticket_sms(ticket, link)
        now = int(time.time())
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            valid_grant(db, grant_hash, now)
            total, by_phone = db.execute(
                "SELECT COUNT(*), SUM(recipient_hash=?) FROM sms_send WHERE created>=?",
                (recipient, now - DAY),
            ).fetchone()
            if total >= daily_limit or (by_phone or 0) >= phone_limit:
                raise HTTPException(429, "ถึงจำนวนส่ง SMS ที่กำหนดสำหรับวันนี้แล้ว")
            db.execute("""INSERT INTO sms_send(ticket_id,evidence_hash,recipient_hash,state,created,expires)
                          VALUES (?,?,?,?,?,?)""", (ticket_id, digest(evidence_token), recipient,
                                                    "pending", now, now + 7 * DAY))

        state, provider_id = "mock", None
        if mode in LIVE_MODES:
            state = "unknown"
            try:
                with httpx.Client(timeout=8, transport=transport) as client:
                    state, provider_id = send_via_provider(client, mode, key, secret, sender, number, message)
            except (httpx.HTTPError, ValueError, AttributeError, TypeError):
                pass
        with database() as db:
            db.execute("UPDATE sms_send SET state=?, provider_id=? WHERE ticket_id=?",
                       (state, provider_id, ticket_id))
        if state == "rejected":
            raise HTTPException(502, "ผู้ให้บริการไม่รับ SMS · ตรวจ sender เครดิต และโดเมนที่อนุมัติ")
        if state == "unknown":
            raise HTTPException(502, "ยังยืนยันผลจากผู้ให้บริการไม่ได้ · ระบบไม่ส่งซ้ำอัตโนมัติ")
        return {"status": state, "provider_message_id": provider_id,
                **({"evidence_url": link, "preview": message} if state == "mock" else {})}

    @app.get("/api/sms/evidence")
    def get_evidence(request: Request):
        with database() as db:
            evidence = evidence_row(db, request)
        try:
            ticket = fetch_ticket(evidence["ticket_id"])
            fields = ("ticket_id", "status", "district", "category", "summary_lines", "location_detail",
                      "created_at", "updated_at", "dispatched_at", "dispatched")
            evidence["tracking"] = {field: ticket[field] for field in fields if field in ticket}
        except (httpx.HTTPError, ValueError):
            pass
        return evidence

    @app.put("/api/sms/evidence/location")
    def save_location(data: Location, request: Request):
        with database() as db:
            evidence = evidence_row(db, request)
            db.execute("UPDATE sms_send SET latitude=?, longitude=?, accuracy=?, updated=? WHERE ticket_id=?",
                       (data.latitude, data.longitude, data.accuracy, int(time.time()), evidence["ticket_id"]))
            return evidence_row(db, request)

    @app.put("/api/sms/evidence/map-link")
    def save_map_link(data: MapLink, request: Request):
        with database() as db:
            evidence = evidence_row(db, request)
            db.execute("UPDATE sms_send SET map_url=?, updated=? WHERE ticket_id=?",
                       (data.map_url, int(time.time()), evidence["ticket_id"]))
            return evidence_row(db, request)

    @app.put("/api/sms/evidence/photo")
    async def save_photo(request: Request):
        with database() as db:
            evidence_row(db, request)
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_PHOTO:
                raise HTTPException(413, "รูปภาพต้องมีขนาดไม่เกิน 5 MB")
            data.extend(chunk)
        try:
            with Image.open(BytesIO(data)) as image:
                media = MIME_TYPES.get(image.format)
                if not media or image.width * image.height > 25_000_000:
                    raise ValueError("Unsupported image")
                image.verify()
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            raise HTTPException(422, "กรุณาใช้รูป JPEG, PNG หรือ WebP ที่เปิดอ่านได้") from None
        with database() as db:
            evidence = evidence_row(db, request)
            db.execute("UPDATE sms_send SET photo=?, photo_type=?, updated=? WHERE ticket_id=?",
                       (bytes(data), media, int(time.time()), evidence["ticket_id"]))
            return evidence_row(db, request)

    @app.get("/api/sms/admin/evidence/{ticket_id}")
    def admin_evidence(ticket_id: str, request: Request):
        admin_only(request)
        with database() as db:
            row = db.execute("""
                SELECT ticket_id, state, provider_id, latitude, longitude, accuracy, map_url,
                photo IS NOT NULL AS has_photo, updated FROM sms_send WHERE ticket_id=?
            """, (ticket_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "ไม่พบข้อมูลคำร้อง")
        return dict(row)

    @app.get("/api/sms/admin/evidence/{ticket_id}/photo")
    def admin_photo(ticket_id: str, request: Request):
        admin_only(request)
        with database() as db:
            row = db.execute("SELECT photo, photo_type FROM sms_send WHERE ticket_id=?", (ticket_id,)).fetchone()
        if row is None or row["photo"] is None:
            raise HTTPException(404, "ไม่พบรูปภาพ")
        return Response(row["photo"], media_type=row["photo_type"],
                        headers={"Content-Disposition": "attachment"})

    return app


def application():
    load_dotenv(Path(__file__).with_name("sms.env"), override=False)
    return create_app()
