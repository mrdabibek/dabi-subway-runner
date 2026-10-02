-- DDL Schema for Neon Runner (PostgreSQL & SQLite compatible)

CREATE TABLE IF NOT EXISTS users (
    id               BIGINT PRIMARY KEY,          -- Telegram User ID (never autoincrement)
    username         VARCHAR(64),
    first_name       VARCHAR(128),
    best_score       INTEGER NOT NULL DEFAULT 0,  -- Distance ran in meters
    total_games      INTEGER NOT NULL DEFAULT 0,
    lives            INTEGER NOT NULL DEFAULT 3 CHECK (lives >= 0),
    last_daily_reset TIMESTAMPTZ,
    referred_by      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    referral_count   INTEGER NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_best_score ON users (best_score DESC);
CREATE INDEX IF NOT EXISTS ix_users_referred_by ON users (referred_by);
