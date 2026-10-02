"""FastAPI backend: Telegram initData authentication, lives economy, and secure score submission.

Endpoints:
  POST /auth          Validate Telegram WebApp initData -> JWT + user snapshot
  POST /start_game    Consume 1 life -> session_id + remaining lives (JWT required)
  POST /submit_score  Validate score vs elapsed time -> update best_score (JWT required)
  GET  /leaderboard   Top N by best_score (public, for WebApp widget)
  GET  /tournament    Prize pool status (100 base, 700 mega at 15,000 players/week)
  GET  /health        Liveness probe
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import parse_qsl

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import get_db, init_db
from api.models import User, check_and_apply_user_milestone, get_tournament

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_TTL_SEC = int(os.getenv("JWT_TTL_SEC", "7200"))

# --- Anti-cheat parameters (keep strictly synchronized with game.js physics) ---
# Score = DISTANCE in meters only (coins are a separate cosmetic counter).
# Game speed starts at 12 u/s, increases +10% every 15s, and is hard-capped at 30 u/s.
# 45 meters/sec + 200m grace covers lag, network latency, and frame skips.
MAX_SCORE_PER_SEC = 45.0
SCORE_GRACE = 200.0          # Flat grace distance for network latency
MIN_PLAY_SEC = 2.0           # Scores > 100 meters in under 2 seconds are instant cheat rejection
MAX_SCORE_ABS = 1_000_000    # Hard ceiling for maximum possible score
SESSION_TTL_SEC = 3600       # Abandon stale gameplay sessions after 1 hour

app = FastAPI(title="Neon Runner API", version="1.0.0")

# Enable CORS for Telegram WebApp access from webviews
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: {session_id: {"uid": int, "start": float}}
SESSIONS: Dict[str, dict] = {}


# ---------------- Pydantic Schemas ----------------

class AuthIn(BaseModel):
    initData: str = Field(..., description="Raw Telegram.WebApp.initData string")


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    best_score: int = 0
    lives: int = 3


class AuthOut(BaseModel):
    token: str
    user: UserOut


class StartGameOut(BaseModel):
    session_id: str
    lives: int
    started_at: float


class ScoreIn(BaseModel):
    session_id: str
    score: int = Field(..., ge=0, le=MAX_SCORE_ABS, description="Distance in meters")
    coins: int = Field(0, ge=0, le=100000, description="Stars collected (cosmetic stat)")


class ScoreOut(BaseModel):
    ok: bool
    score: int
    coins: int = 0
    best_score: int
    is_new_best: bool
    elapsed_sec: float


class LeaderboardEntry(BaseModel):
    id: int
    username: Optional[str] = None
    best_score: int


class LeaderboardOut(BaseModel):
    top: List[LeaderboardEntry]


class ClaimBoxOut(BaseModel):
    ok: bool
    reward_type: str
    reward_amount: int
    lives: int
    message: str


# ---------------- Telegram initData Validation ----------------

def validate_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData string using SHA256 HMAC as per official specs.

    Specification:
    1. Parse query string into key-value pairs.
    2. Extract and remove 'hash'.
    3. Sort remaining keys alphabetically and join as 'key=value\n'.
    4. Compute secret_key = HMAC_SHA256("WebAppData", BOT_TOKEN).
    5. Compute calculated_hash = HMAC_SHA256(secret_key, data_check_string).hexdigest().
    6. Compare using hmac.compare_digest.
    7. Verify auth_date is not older than 24 hours.
    """
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN is not configured on the server")
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=401, detail="initData missing hash signature")

    # Construct data_check_string from sorted pairs
    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
    
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram hash signature")

    # Replay protection: verify auth_date within 24 hours (86,400 seconds)
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid auth_date format in initData")

    now = time.time()
    if auth_date > now + 300:
        raise HTTPException(status_code=401, detail="Invalid future auth_date in initData")
    if now - auth_date > 86400:
        raise HTTPException(status_code=401, detail="initData expired (>24h), please reopen from Telegram")

    return pairs


def decode_user_from_pairs(pairs: dict) -> tuple[int, Optional[str], Optional[str]]:
    """Extract (uid, username, first_name) from parsed initData."""
    try:
        user_dict = json.loads(pairs.get("user", "{}"))
        uid = int(user_dict["id"])
    except Exception:
        raise HTTPException(status_code=401, detail="initData does not contain a valid user.id")
    return uid, user_dict.get("username"), user_dict.get("first_name")


def issue_jwt(uid: int) -> str:
    """Generate a signed JWT token with 2 hours TTL."""
    now = datetime.now(timezone.utc)
    payload = {
        "uid": uid,
        "iat": now,
        "exp": now + timedelta(seconds=JWT_TTL_SEC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def require_uid(authorization: str = Header(default="")) -> int:
    """FastAPI dependency extracting and verifying user ID from 'Authorization: Bearer <token>'."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token. Please authenticate via /auth first")
    
    token = authorization[7:].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["uid"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please reopen the game")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session token")


def get_or_create_user(db: Session, uid: int, username: Optional[str], first_name: Optional[str]) -> User:
    """Find existing user or register a new one, triggering daily lives reset if due."""
    user = db.get(User, uid)
    if user is None:
        user = User(id=uid, username=username, first_name=first_name)
        db.add(user)
        db.commit()
        db.refresh(user)
        check_and_apply_user_milestone(db)
    else:
        # Keep profile names updated
        if username and user.username != username:
            user.username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        db.commit()

    user.ensure_daily_reset()
    db.commit()
    return user


# ---------------- API Endpoints ----------------

@app.on_event("startup")
def on_startup() -> None:
    """Initialize database tables on app startup."""
    if len(JWT_SECRET) < 32 or JWT_SECRET == "replace-with-a-random-secret-at-least-32-characters":
        raise RuntimeError("JWT_SECRET kamida 32 belgilik tasodifiy kalit bo'lishi kerak")
    init_db()


@app.get("/health")
def health() -> dict:
    """Liveness check endpoint."""
    return {"ok": True}


@app.post("/auth", response_model=AuthOut)
def auth(body: AuthIn, db: Session = Depends(get_db)) -> AuthOut:
    """Authenticate Telegram WebApp session using initData and issue JWT."""
    pairs = validate_init_data(body.initData)
    uid, username, first_name = decode_user_from_pairs(pairs)
    user = get_or_create_user(db, uid, username, first_name)
    
    return AuthOut(
        token=issue_jwt(uid),
        user=UserOut(
            id=user.id,
            username=user.username,
            best_score=user.best_score,
            lives=user.lives,
        ),
    )


@app.post("/start_game", response_model=StartGameOut)
def start_game(uid: int = Depends(require_uid), db: Session = Depends(get_db)) -> StartGameOut:
    """Begin a gameplay session: deduct 1 life and record session timestamp."""
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user. Please call /auth first")

    user.ensure_daily_reset()
    if user.lives <= 0:
        # HTTP 402 signals to frontend that lives are depleted and invite modal must show
        raise HTTPException(status_code=402, detail="No lives left. Invite a friend to get +1 life!")

    user.lives -= 1
    user.total_games += 1
    db.commit()

    session_id = uuid.uuid4().hex
    now = time.time()
    SESSIONS[session_id] = {"uid": uid, "start": now}

    # Clean up any stale sessions (> 1 hour old)
    stale_keys = [sid for sid, data in SESSIONS.items() if now - data["start"] > SESSION_TTL_SEC]
    for sid in stale_keys:
        SESSIONS.pop(sid, None)

    return StartGameOut(session_id=session_id, lives=user.lives, started_at=now)


@app.post("/submit_score", response_model=ScoreOut)
def submit_score(
    body: ScoreIn,
    uid: int = Depends(require_uid),
    db: Session = Depends(get_db),
) -> ScoreOut:
    """Verify gameplay session and record run score (meters) with anti-cheat checks."""
    session = SESSIONS.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=400, detail="Unknown or expired session. Start game via /start_game")
    if session["uid"] != uid:
        raise HTTPException(status_code=403, detail="Session belongs to a different user")

    elapsed = max(0.0, time.time() - session["start"])
    # Delete session immediately (single-use token prevents replay attacks)
    SESSIONS.pop(body.session_id, None)

    # --- Strict Anti-Cheat Validation Rules ---
    # 1. Absolute bounds check
    if body.score < 0 or body.score > MAX_SCORE_ABS:
        raise HTTPException(status_code=400, detail="Score value out of acceptable range")

    # 2. Impossible instant teleportation check
    if body.score > 100 and elapsed < MIN_PLAY_SEC:
        raise HTTPException(status_code=400, detail="CHEAT_DETECTED: Impossible score for elapsed time")

    # 3. Maximum speed limit check: score (meters) cannot exceed max speed * elapsed + grace
    allowed_max_distance = elapsed * MAX_SCORE_PER_SEC + SCORE_GRACE
    if body.score > allowed_max_distance:
        raise HTTPException(
            status_code=400,
            detail=f"CHEAT_DETECTED: Score {body.score}m exceeds theoretical maximum ({allowed_max_distance:.0f}m in {elapsed:.1f}s)",
        )

    # 4. Realistic coin bound check
    max_coins = (body.score // 4) + 60
    if body.coins > max_coins:
        body.coins = max_coins

    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="User record not found")

    is_new_best = body.score > user.best_score
    if is_new_best:
        user.best_score = body.score

    # --- Referral Anti-Abuse: Award inviter ONLY after real game played ---
    if body.score > 10 and user.referred_by is not None and not getattr(user, "referral_rewarded", False):
        user.referral_rewarded = True
        inviter = db.get(User, user.referred_by)
        if inviter is not None:
            inviter.lives += 1
            inviter.referral_count += 1
            db.commit()
            try:
                import urllib.parse
                import urllib.request
                from bot.bot import BOT_TOKEN
                if BOT_TOKEN:
                    f_name = f"@{user.username}" if user.username else (user.first_name or f"ID: {user.id}")
                    notif_text = (
                        f"🎉 <b>Do'stingiz {f_name} o'yinni o'ynadi!</b>\n"
                        f"Sizga <b>+1 jon (❤️)</b> taqdim etildi!\n"
                        f"Hozirgi jonlaringiz: <b>{inviter.lives}</b> ta"
                    )
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={inviter.id}&text={urllib.parse.quote(notif_text)}&parse_mode=HTML"
                    urllib.request.urlopen(url, timeout=3.0)
            except Exception as ex:
                pass

    db.commit()

    return ScoreOut(
        ok=True,
        score=body.score,
        coins=body.coins,
        best_score=user.best_score,
        is_new_best=is_new_best,
        elapsed_sec=round(elapsed, 2),
    )


@app.get("/tournament")
def tournament_status(db: Session = Depends(get_db)) -> dict:
    """Return prize pool status: Top-5 distribution (100, 50, 15, 10, 5) or 700 MEGA."""
    return get_tournament(db)


@app.get("/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(limit: int = 10, db: Session = Depends(get_db)) -> LeaderboardOut:
    """Return top players ranked by best_score in descending order."""
    clamped_limit = max(1, min(limit, 50))
    top_users = db.query(User).order_by(User.best_score.desc()).limit(clamped_limit).all()
    
    return LeaderboardOut(
        top=[
            LeaderboardEntry(id=u.id, username=u.username, best_score=u.best_score)
            for u in top_users
        ]
    )


@app.post("/claim_box", response_model=ClaimBoxOut)
def claim_box(uid: int = Depends(require_uid), db: Session = Depends(get_db)) -> ClaimBoxOut:
    """Open a mystery box collected during the run and award random bonus."""
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="User record not found")

    user.ensure_daily_reset()
    import random
    roll = random.random()
    if roll < 0.60:
        user.lives += 1
        reward_type = "life"
        amount = 1
        msg = "🎉 Tabriklaymiz! Sizga +1 Jon (❤️) taqdim etildi!"
    elif roll < 0.90:
        reward_type = "coins"
        amount = 50
        msg = "🎉 Tabriklaymiz! Sizga +50 Tanga (🪙) taqdim etildi!"
    else:
        reward_type = "coins"
        amount = 100
        msg = "🔥 JACKPOT! Sizga +100 Tanga (🪙) taqdim etildi!"

    db.commit()
    return ClaimBoxOut(
        ok=True,
        reward_type=reward_type,
        reward_amount=amount,
        lives=user.lives,
        message=msg,
    )


# --- Static WebApp Mounting ---
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

webapp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
if os.path.exists(webapp_dir):
    app.mount("/webapp", StaticFiles(directory=webapp_dir, html=True), name="webapp")

    @app.get("/", include_in_schema=False)
    def root_redirect():
        """Redirect root URL directly to the WebApp."""
        return RedirectResponse(url="/webapp/")

    @app.get("/game", include_in_schema=False)
    def game_redirect():
        """Redirect /game directly to the WebApp."""
        return RedirectResponse(url="/webapp/")
