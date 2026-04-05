CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    donated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    campaign_name TEXT,
    frequency TEXT NOT NULL DEFAULT 'One-time',
    status TEXT NOT NULL DEFAULT 'Completed',
    transaction_id TEXT NOT NULL UNIQUE,
    payment_id TEXT,
    razorpay_order_id TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_donations_user_id
    ON donations(user_id);

CREATE INDEX IF NOT EXISTS idx_donations_donated_at
    ON donations(donated_at DESC);
