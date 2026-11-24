-- Целевая СУБД: SQLite. Время: UTC, ISO 8601 одного формата.
PRAGMA foreign_keys = ON;

CREATE TABLE acquisition_sources (
    source_id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE
);

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    registered_at TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES acquisition_sources(source_id),
    sport_interest TEXT,
    email_consent INTEGER NOT NULL CHECK (email_consent IN (0, 1)),
    community_consent INTEGER NOT NULL CHECK (community_consent IN (0, 1))
);

CREATE TABLE events (
    event_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    event_at TEXT NOT NULL,
    event_name TEXT NOT NULL CHECK (event_name IN (
        'article_opened', 'article_read', 'interest_selected',
        'communication_sent', 'community_joined', 'communication_opted_out'
    )),
    channel TEXT CHECK (channel IN ('email', 'community'))
);

CREATE INDEX idx_events_user_time ON events(user_id, event_at);

CREATE TABLE experiment_assignments (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
    assigned_at TEXT NOT NULL,
    variant TEXT NOT NULL CHECK (variant IN ('email', 'community'))
);

CREATE TABLE acquisition_costs (
    source_id INTEGER NOT NULL REFERENCES acquisition_sources(source_id),
    cost_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (source_id, cost_date)
);

-- Последний полностью наблюдаемый календарный день, включительно.
CREATE TABLE dataset_metadata (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    observation_end_date TEXT NOT NULL,
    random_seed INTEGER NOT NULL
);
