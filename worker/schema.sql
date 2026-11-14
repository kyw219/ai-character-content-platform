PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS oauth_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  encrypted_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
  id TEXT PRIMARY KEY,
  scheduled_at TEXT NOT NULL,
  caption TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PLANNED',
  posting_phase TEXT NOT NULL DEFAULT '',
  publish_attempts INTEGER NOT NULL DEFAULT 0,
  last_attempt_at TEXT NOT NULL DEFAULT '',
  next_retry_at TEXT NOT NULL DEFAULT '',
  platform_post_id TEXT NOT NULL DEFAULT '',
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS posts_due_idx
  ON posts(status, scheduled_at, next_retry_at);
