"""SQLAlchemy 2.0 models and tournament helpers for Neon Runner (api package)."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

try:
    from api.database import Base
except ImportError:
    from database import Base

DAILY_LIVES = 3
RESET_INTERVAL = dt.timedelta(hours=24)

PRIZE_BASE = int(os.getenv("PRIZE_BASE", "100"))
PRIZE_MEGA = int(os.getenv("PRIZE_MEGA", "700"))
MEGA_GOAL = int(os.getenv("MEGA_GOAL", "15000"))
TOURNAMENT_DAYS = int(os.getenv("TOURNAMENT_DAYS", "7"))


def utcnow() -> dt.datetime:
    """Return timezone-aware current UTC datetime."""
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    """User entity representing a Telegram player.

    - id: Telegram user ID (BigInteger, not autoincremented)
    - best_score: farthest distance achieved in meters
    - lives: remaining runs available (replenished daily or earned via referrals)
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)

    best_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lives: Mapped[int] = mapped_column(Integer, nullable=False, default=DAILY_LIVES)
    last_daily_reset: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Retain legacy column so existing SQLite databases can still insert users.
    _legacy_is_subscribed: Mapped[bool] = mapped_column("is_subscribed", Boolean, nullable=False, default=False)

    # Referral system: Self-referential Foreign Key
    referred_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, default=None
    )
    referral_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    referral_rewarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("ix_users_best_score", best_score.desc()),
        Index("ix_users_referred_by", referred_by),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} @{self.username} best={self.best_score}m lives={self.lives}>"

    # -- Lives Management Helpers --

    def needs_reset(self, now: dt.datetime | None = None) -> bool:
        """Check if 24 hours have elapsed since the last daily refill."""
        now = now or utcnow()
        if self.last_daily_reset is None:
            return True
        last = self.last_daily_reset
        if last.tzinfo is None:
            # Handle naive datetimes from SQLite
            last = last.replace(tzinfo=dt.timezone.utc)
        return (now - last) >= RESET_INTERVAL

    def ensure_daily_reset(self, now: dt.datetime | None = None) -> bool:
        """Refill lives to at least DAILY_LIVES (3) if 24 hours have passed. Returns True if reset."""
        now = now or utcnow()
        if self.needs_reset(now):
            self.lives = max(self.lives or 0, DAILY_LIVES)
            self.last_daily_reset = now
            return True
        return False


class SystemSetting(Base):
    """Key-value table for global parameters (e.g. 1,000 user milestones)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)


def check_and_apply_user_milestone(db: Any) -> int:
    """Checks if a new 1,000-user milestone has been reached.
    
    If so, awards +3 lives to ALL registered players and updates the milestone.
    Returns the milestone reached (e.g. 1000, 2000), or 0 if no new milestone.
    """
    total_users: int = db.query(func.count(User.id)).scalar() or 0
    current_milestone = (total_users // 1000) * 1000
    if current_milestone < 1000:
        return 0

    setting = db.get(SystemSetting, "last_awarded_milestone")
    last_awarded = int(setting.value) if setting else 0

    if current_milestone > last_awarded:
        # Har 1000 ta foydalanuvchi uchun barchaga +3 tadan jon beriladi!
        db.query(User).update({User.lives: User.lives + 3})
        if setting:
            setting.value = str(current_milestone)
        else:
            db.add(SystemSetting(key="last_awarded_milestone", value=str(current_milestone)))
        db.commit()
        return current_milestone
    return 0


PRIZE_DISTRIBUTION = [
    {"place": 1, "stars": 100, "mega_stars": 400, "medal": "🥇"},
    {"place": 2, "stars": 50, "mega_stars": 150, "medal": "🥈"},
    {"place": 3, "stars": 15, "mega_stars": 80, "medal": "🥉"},
    {"place": 4, "stars": 10, "mega_stars": 45, "medal": "4️⃣"},
    {"place": 5, "stars": 5, "mega_stars": 25, "medal": "5️⃣"},
]


def get_tournament(db: Any) -> Dict[str, Any]:
    """Calculate tournament status and prize pool.

    The tournament week starts at MIN(created_at) across all players.
    Base prize pool is 180 Stars across Top-5 (100, 50, 15, 10, 5); upgrades to 700 MEGA if participants >= 15,000.
    """
    now = utcnow()
    participants: int = db.query(func.count(User.id)).scalar() or 0
    first: dt.datetime | None = db.query(func.min(User.created_at)).scalar()

    if first is not None:
        if first.tzinfo is None:
            first = first.replace(tzinfo=dt.timezone.utc)
        start = first
    else:
        start = now

    deadline = start + dt.timedelta(days=TOURNAMENT_DAYS)
    seconds_left = (deadline - now).total_seconds()
    days_left = max(0.0, seconds_left / 86400.0)

    mega_unlocked = participants >= MEGA_GOAL
    total_prize = PRIZE_MEGA if mega_unlocked else 180
    progress_to_next_1000 = participants % 1000

    return {
        "participants": participants,
        "goal": MEGA_GOAL,
        "base_prize": 180,
        "mega_prize": PRIZE_MEGA,
        "prize": total_prize,
        "total_prize_fund": total_prize,
        "mega_unlocked": mega_unlocked,
        "days_left": round(days_left, 1),
        "deadline": deadline.isoformat(),
        "milestone_progress": progress_to_next_1000,
        "milestone_target": 1000,
        "prizes": [
            {
                "place": p["place"],
                "rank": p["place"],
                "stars": p["mega_stars"] if mega_unlocked else p["stars"],
                "base_stars": p["stars"],
                "mega_stars": p["mega_stars"],
                "medal": p["medal"],
            }
            for p in PRIZE_DISTRIBUTION
        ],
    }
