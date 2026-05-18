from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from config import DB_PATH
from security import create_token, expires_at_iso, utc_now_iso


class Storage:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    stripe_customer_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    device_name TEXT NOT NULL,
                    connector_version TEXT NOT NULL,
                    device_token TEXT NOT NULL UNIQUE,
                    last_seen_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS library_roots (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                    label TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    last_scan_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(device_id, folder_path)
                );

                CREATE TABLE IF NOT EXISTS clips (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
                    root_id TEXT NOT NULL REFERENCES library_roots(id) ON DELETE CASCADE,
                    relative_path TEXT NOT NULL,
                    title_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    character TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    size_mb REAL NOT NULL,
                    modified_at TEXT NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    fps REAL,
                    frames INTEGER,
                    duration_sec REAL,
                    aspect_ratio TEXT,
                    looks_cleaned INTEGER NOT NULL,
                    search_text TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(root_id, relative_path)
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stripe_subscription_id TEXT,
                    stripe_price_id TEXT,
                    current_period_end TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);
                CREATE INDEX IF NOT EXISTS idx_library_roots_user_id ON library_roots(user_id);
                CREATE INDEX IF NOT EXISTS idx_clips_user_id ON clips(user_id);
                CREATE INDEX IF NOT EXISTS idx_clips_root_id ON clips(root_id);
                """
            )

    def create_user(self, email: str, display_name: str, password_hash: str) -> dict:
        now = utc_now_iso()
        user_id = create_token("usr")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (id, email, display_name, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, email, display_name, password_hash, now),
            )
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.*, subscriptions.plan_id, subscriptions.status AS subscription_status,
                       subscriptions.current_period_end
                FROM users
                LEFT JOIN subscriptions ON subscriptions.user_id = users.id
                WHERE users.id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            raise KeyError("User not found.")
        return dict(row)

    def get_user_by_email(self, email: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def create_session(self, user_id: str, ttl_hours: int) -> str:
        token = create_token("sess")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user_id, utc_now_iso(), expires_at_iso(ttl_hours)),
            )
        return token

    def get_user_by_session(self, token: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.*, subscriptions.plan_id, subscriptions.status AS subscription_status,
                       subscriptions.current_period_end
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                LEFT JOIN subscriptions ON subscriptions.user_id = users.id
                WHERE sessions.token = ? AND sessions.expires_at > ?
                """,
                (token, utc_now_iso()),
            ).fetchone()
        return dict(row) if row else None

    def register_device(self, user_id: str, device_name: str, connector_version: str) -> dict:
        now = utc_now_iso()
        with self.connect() as connection:
            existing = connection.execute(
                """
                SELECT id, device_token
                FROM devices
                WHERE user_id = ? AND device_name = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, device_name),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE devices
                    SET connector_version = ?, last_seen_at = ?
                    WHERE id = ?
                    """,
                    (connector_version, now, existing["id"]),
                )
                return {"device_id": existing["id"], "device_token": existing["device_token"]}

            device_id = create_token("dev")
            device_token = create_token("dvt")
            connection.execute(
                """
                INSERT INTO devices (id, user_id, device_name, connector_version, device_token, last_seen_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, user_id, device_name, connector_version, device_token, now, now),
            )
        return {"device_id": device_id, "device_token": device_token}

    def get_device_by_token(self, device_token: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM devices WHERE device_token = ?", (device_token,)).fetchone()
        return dict(row) if row else None

    def count_devices(self, user_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM devices WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["count"]) if row else 0

    def get_device_by_user_and_name(self, user_id: str, device_name: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM devices
                WHERE user_id = ? AND device_name = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, device_name),
            ).fetchone()
        return dict(row) if row else None

    def count_roots(self, user_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM library_roots WHERE user_id = ?", (user_id,)).fetchone()
        return int(row["count"]) if row else 0

    def touch_device(self, device_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE devices SET last_seen_at = ? WHERE id = ?",
                (utc_now_iso(), device_id),
            )

    def get_root_by_device_and_path(self, device_id: str, folder_path: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM library_roots WHERE device_id = ? AND folder_path = ?",
                (device_id, folder_path),
            ).fetchone()
        return dict(row) if row else None

    def upsert_library_root(self, user_id: str, device_id: str, label: str, folder_path: str) -> str:
        now = utc_now_iso()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM library_roots WHERE device_id = ? AND folder_path = ?",
                (device_id, folder_path),
            ).fetchone()
            if existing:
                root_id = existing["id"]
                connection.execute(
                    """
                    UPDATE library_roots
                    SET label = ?, last_scan_at = ?
                    WHERE id = ?
                    """,
                    (label, now, root_id),
                )
                return root_id
            root_id = create_token("root")
            connection.execute(
                """
                INSERT INTO library_roots (id, user_id, device_id, label, folder_path, last_scan_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (root_id, user_id, device_id, label, folder_path, now, now),
            )
            return root_id

    def clear_root_clips(self, root_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM clips WHERE root_id = ?", (root_id,))

    def insert_clips(self, user_id: str, device_id: str, root_id: str, clips: Iterable[dict]) -> None:
        rows = []
        now = utc_now_iso()
        for clip in clips:
            clip_id = create_token("clip")
            rows.append(
                (
                    clip_id,
                    user_id,
                    device_id,
                    root_id,
                    clip["relative_path"],
                    clip["title_text"],
                    clip.get("category", ""),
                    clip.get("character", ""),
                    clip["filename"],
                    clip.get("extension", ".mp4"),
                    clip.get("size_bytes", 0),
                    clip.get("size_mb", 0.0),
                    clip["modified_at"],
                    clip.get("width"),
                    clip.get("height"),
                    clip.get("fps"),
                    clip.get("frames"),
                    clip.get("duration_sec"),
                    clip.get("aspect_ratio"),
                    1 if clip.get("looks_cleaned") else 0,
                    clip["search_text"],
                    clip["source_hash"],
                    now,
                    now,
                )
            )
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO clips (
                    id, user_id, device_id, root_id, relative_path, title_text, category, character,
                    filename, extension, size_bytes, size_mb, modified_at, width, height, fps,
                    frames, duration_sec, aspect_ratio, looks_cleaned, search_text, source_hash,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_dashboard(self, user_id: str) -> dict:
        with self.connect() as connection:
            subscription = connection.execute(
                "SELECT * FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            devices = connection.execute(
                "SELECT id, device_name, connector_version, last_seen_at, created_at FROM devices WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            roots = connection.execute(
                """
                SELECT library_roots.id, library_roots.label, library_roots.folder_path, library_roots.last_scan_at,
                       devices.device_name,
                       COUNT(clips.id) AS clip_count
                FROM library_roots
                JOIN devices ON devices.id = library_roots.device_id
                LEFT JOIN clips ON clips.root_id = library_roots.id
                WHERE library_roots.user_id = ?
                GROUP BY library_roots.id
                ORDER BY library_roots.created_at DESC
                """,
                (user_id,),
            ).fetchall()
            recent_clips = connection.execute(
                """
                SELECT id, title_text, category, character, relative_path, duration_sec, looks_cleaned, modified_at
                FROM clips
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT 24
                """,
                (user_id,),
            ).fetchall()
            summary = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM clips WHERE user_id = ?) AS clip_count,
                    (SELECT COUNT(*) FROM library_roots WHERE user_id = ?) AS root_count,
                    (SELECT COUNT(*) FROM devices WHERE user_id = ?) AS device_count,
                    (SELECT COALESCE(SUM(size_bytes), 0) FROM clips WHERE user_id = ?) AS total_bytes
                """,
                (user_id, user_id, user_id, user_id),
            ).fetchone()
            categories = connection.execute(
                "SELECT DISTINCT category FROM clips WHERE user_id = ? AND category != '' ORDER BY category ASC",
                (user_id,),
            ).fetchall()
            characters = connection.execute(
                "SELECT DISTINCT character FROM clips WHERE user_id = ? AND character != '' ORDER BY character ASC",
                (user_id,),
            ).fetchall()
        return {
            "subscription": dict(subscription) if subscription else None,
            "devices": [dict(row) for row in devices],
            "roots": [dict(row) for row in roots],
            "recent_clips": [dict(row) for row in recent_clips],
            "summary": dict(summary) if summary else {"clip_count": 0, "root_count": 0, "device_count": 0, "total_bytes": 0},
            "categories": [row["category"] for row in categories],
            "characters": [row["character"] for row in characters],
        }

    def search_clips(
        self,
        user_id: str,
        *,
        keywords: list[str],
        categories: list[str],
        characters: list[str],
        cleaned_filter: str,
        limit: int,
    ) -> list[dict]:
        sql = """
            SELECT id, title_text, category, character, relative_path, duration_sec, looks_cleaned,
                   size_mb, modified_at, search_text
            FROM clips
            WHERE user_id = ?
        """
        params: list = [user_id]
        if categories:
            sql += " AND category IN ({})".format(",".join("?" for _ in categories))
            params.extend(categories)
        if characters:
            sql += " AND character IN ({})".format(",".join("?" for _ in characters))
            params.extend(characters)
        if cleaned_filter == "only_cleaned":
            sql += " AND looks_cleaned = 1"
        elif cleaned_filter == "only_uncleaned":
            sql += " AND looks_cleaned = 0"
        if keywords:
            sql += " AND (" + " OR ".join("LOWER(search_text) LIKE ?" for _ in keywords) + ")"
            params.extend([f"%{keyword.lower()}%" for keyword in keywords])
        sql += " ORDER BY modified_at DESC LIMIT 300"
        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        def score(row: dict) -> float:
            haystack = f"{row['title_text']} {row['search_text']} {row['relative_path']}".lower()
            value = 0.0
            for keyword in keywords:
                if keyword.lower() in haystack:
                    value += 6.0 if " " in keyword else 2.5
            if row["category"] in categories:
                value += 8.0
            if row["character"] in characters:
                value += 10.0
            if row["looks_cleaned"]:
                value += 0.5
            return value

        ranked = []
        for row in rows:
            row["score"] = round(score(row), 3)
            ranked.append(row)
        ranked.sort(key=lambda row: (-row["score"], row["category"].lower(), row["title_text"].lower()))
        return ranked[:limit]

    def set_subscription(
        self,
        user_id: str,
        *,
        plan_id: str,
        status: str,
        stripe_subscription_id: str | None,
        stripe_price_id: str | None,
        current_period_end: str | None,
    ) -> None:
        now = utc_now_iso()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE subscriptions
                    SET plan_id = ?, status = ?, stripe_subscription_id = ?, stripe_price_id = ?,
                        current_period_end = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    (plan_id, status, stripe_subscription_id, stripe_price_id, current_period_end, now, user_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO subscriptions (
                        id, user_id, plan_id, status, stripe_subscription_id, stripe_price_id,
                        current_period_end, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (create_token("sub"), user_id, plan_id, status, stripe_subscription_id, stripe_price_id, current_period_end, now, now),
                )

    def set_stripe_customer_id(self, user_id: str, stripe_customer_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                (stripe_customer_id, user_id),
            )

    def get_user_by_stripe_customer(self, stripe_customer_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE stripe_customer_id = ?",
                (stripe_customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def export_json(self) -> str:
        with self.connect() as connection:
            payload = {
                "users": [dict(row) for row in connection.execute("SELECT id, email, display_name, stripe_customer_id, created_at FROM users")],
                "devices": [dict(row) for row in connection.execute("SELECT * FROM devices")],
                "roots": [dict(row) for row in connection.execute("SELECT * FROM library_roots")],
            }
        return json.dumps(payload, indent=2)
