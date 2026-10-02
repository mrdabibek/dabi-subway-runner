-- Raw SQL reference for the `users` table (SQLite + PostgreSQL compatible).
-- The app itself uses SQLAlchemy (api/models.py); this file is documentation / manual setup.

CREATE TABLE IF NOT EXISTS users (
    id             BIGINT PRIMARY KEY,          -- Telegram user id
    username       VARCHAR(64),
    first_name     VARCHAR(128),
    best_score     INTEGER NOT NULL DEFAULT 0,
    total_games    INTEGER NOT NULL DEFAULT 0,
    lives          INTEGER NOT NULL DEFAULT 3 CHECK (lives >= 0),
    last_daily_reset TIMESTAMPTZ,
    referred_by    BIGINT REFERENCES users(id) ON DELETE SET NULL,
    referral_count INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_best_score ON users (best_score DESC);
CREATE INDEX IF NOT EXISTS ix_users_referred_by ON users (referred_by);
