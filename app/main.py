import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.database import database, initialize_database
from app.recommendations import (ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES,
                                 generate_recommendation, retailer_search_url)
from app.schemas import Recommendation
from app.security import COOKIE_NAME, SESSION_SECONDS, create_session, hash_password, session_user_id, verify_password

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="PocketSmart AI", version="1.0.0", description="Budget-aware lifestyle planning recommendations.", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


class RegisterInput(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=10, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def current_user(request: Request):
    user_id = session_user_id(request.cookies.get(COOKIE_NAME))
    if user_id is None:
        return None
    with database() as db:
        row = db.execute("SELECT id, email, display_name FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(COOKIE_NAME, create_session(user_id), max_age=SESSION_SECONDS,
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"user": current_user(request)})


@app.get("/api/health")
async def health():
    return {"status": "ok", "recommendation_mode": "gemini" if settings.gemini_api_key else "demo"}


@app.get("/api/session")
async def session_info(request: Request):
    return {"user": current_user(request)}


@app.post("/api/register", status_code=201)
async def register(data: RegisterInput, response: Response):
    email = str(data.email).lower()
    if not data.display_name.strip():
        raise HTTPException(status_code=422, detail="Enter a name for your account.")
    with database() as db:
        try:
            cur = db.execute("INSERT INTO users(email, display_name, password_hash) VALUES(?,?,?)",
                (email, data.display_name.strip(), hash_password(data.password)))
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
            raise
    set_session_cookie(response, cur.lastrowid)
    return {"user": {"id": cur.lastrowid, "email": email, "display_name": data.display_name.strip()}}


@app.post("/api/login")
async def login(data: LoginInput, response: Response):
    with database() as db:
        row = db.execute("SELECT id, email, display_name, password_hash FROM users WHERE email=?", (str(data.email).lower(),)).fetchone()
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    set_session_cookie(response, row["id"])
    return {"user": {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}}


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")
    return {"ok": True}


def validate_planner_payload(planner: str, raw: str) -> dict:
    if planner not in {"home", "party", "jewelry"}:
        raise HTTPException(status_code=404, detail="Unknown planner.")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Planner details must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Planner details must be an object.")
    try:
        budget = float(data.get("budget", 0))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Budget must be a number.") from exc
    if budget <= 0 or budget > 10_000_000:
        raise HTTPException(status_code=422, detail="Budget must be between ₹1 and ₹1,00,00,000.")
    data["budget"] = round(budget, 2)
    for field in ("style", "room_types", "event_type", "venue", "occasion", "outfit_notes"):
        value = data.get(field, "")
        if isinstance(value, list):
            value = ", ".join(str(v)[:50] for v in value[:8])
        if not isinstance(value, str):
            value = str(value)
        data[field] = value.strip()[:240]
    if planner == "home" and not data.get("room_types"):
        raise HTTPException(status_code=422, detail="Enter at least one room or area.")
    if planner == "party":
        try:
            guests = int(data.get("guests", 0))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Guest count must be a whole number.") from exc
        if not 1 <= guests <= 5000:
            raise HTTPException(status_code=422, detail="Guest count must be between 1 and 5,000.")
        data["guests"] = guests
        if not data.get("event_type"):
            raise HTTPException(status_code=422, detail="Choose an event type.")
    if planner == "jewelry" and not data.get("occasion"):
        raise HTTPException(status_code=422, detail="Enter an occasion.")
    return data


@app.post("/api/recommendations/{planner}")
async def recommendations(planner: str, request: Request, payload: str = Form(...), image: UploadFile | None = File(default=None)):
    data = validate_planner_payload(planner, payload)
    image_bytes = None
    image_mime = None
    if image is not None and image.filename:
        if planner != "jewelry":
            raise HTTPException(status_code=422, detail="Images are only supported by the jewelry planner.")
        image_mime = image.content_type or ""
        if image_mime not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WebP image.")
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
        await image.close()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be 5 MB or smaller.")
        valid_signature = ((image_mime == "image/jpeg" and image_bytes.startswith(b"\xff\xd8\xff")) or
            (image_mime == "image/png" and image_bytes.startswith(b"\x89PNG\r\n\x1a\n")) or
            (image_mime == "image/webp" and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP"))
        if not valid_signature:
            raise HTTPException(status_code=415, detail="The uploaded file does not match its image type.")
    try:
        result: Recommendation = await asyncio.to_thread(generate_recommendation, planner, data, image_bytes, image_mime)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    response_data = result.model_dump()
    for item in response_data["items"]:
        item["search_url"] = retailer_search_url(item["retailer"], item["search_query"] or item["title"])
    user = current_user(request) if request else None
    if user:
        with database() as db:
            db.execute("INSERT INTO history(user_id, planner, request_json, result_json) VALUES(?,?,?,?)",
                (user["id"], planner, json.dumps(data), json.dumps(response_data)))
    return response_data


@app.get("/api/history")
async def history(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to view saved history.")
    with database() as db:
        rows = db.execute("SELECT id, planner, request_json, result_json, created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT 30", (user["id"],)).fetchall()
    return {"items": [{"id": row["id"], "planner": row["planner"], "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]), "created_at": row["created_at"]} for row in rows]}
