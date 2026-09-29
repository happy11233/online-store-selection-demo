"""Local demo authentication: Argon2 passwords and revocable SQLite sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import settings

COOKIE_NAME = "aimid_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}


class AuthStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._attempt_lock = Lock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, csrf_token TEXT NOT NULL, expires_at INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def _public_user(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    def initialized(self) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def bootstrap(self, username: str, password: str) -> dict[str, Any]:
        password_hash = self.hasher.hash(password)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ValueError("管理员已初始化")
            cursor = db.execute("INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)", (username, password_hash, int(time.time())))
            return {"id": cursor.lastrowid, "username": username, "role": "admin"}

    def create_user(self, username: str, password: str, role: str) -> dict[str, Any]:
        password_hash = self.hasher.hash(password)
        try:
            with self._connect() as db:
                cursor = db.execute("INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)", (username, password_hash, role, int(time.time())))
                return {"id": cursor.lastrowid, "username": username, "role": role}
        except sqlite3.IntegrityError as error:
            raise ValueError("用户名已存在") from error

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [self._public_user(row) for row in db.execute("SELECT id, username, role FROM users ORDER BY id")]

    def login(self, username: str, password: str, client_host: str) -> tuple[str, dict[str, Any]] | None:
        attempt_key = client_host + ":" + username.lower()
        now = time.time()
        with self._attempt_lock:
            recent = [stamp for stamp in self._attempts[attempt_key] if now - stamp < 600]
            self._attempts[attempt_key] = recent
            if len(recent) >= 5:
                raise PermissionError("登录尝试过多，请十分钟后重试")
        with self._connect() as db:
            row = db.execute("SELECT id, username, role, password_hash FROM users WHERE username = ?", (username,)).fetchone()
            try:
                valid = row is not None and self.hasher.verify(row["password_hash"], password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                valid = False
            if not valid:
                with self._attempt_lock:
                    self._attempts[attempt_key].append(now)
                return None
            with self._attempt_lock:
                self._attempts.pop(attempt_key, None)
            token = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            expires_at = int(now) + SESSION_TTL_SECONDS
            db.execute("INSERT INTO sessions(token_hash, user_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], csrf_token, expires_at))
            return token, {**self._public_user(row), "csrf_token": csrf_token, "expires_at": expires_at}

    def session(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as db:
            row = db.execute("SELECT users.id, users.username, users.role, sessions.csrf_token, sessions.expires_at FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ?", (token_hash,)).fetchone()
            if not row:
                return None
            if row["expires_at"] <= int(time.time()):
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                return None
            return {**self._public_user(row), "csrf_token": row["csrf_token"], "expires_at": row["expires_at"]}

    def logout(self, token: str | None) -> None:
        if token:
            with self._connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))


def csrf_valid(session: dict[str, Any], supplied: str | None) -> bool:
    return bool(supplied and hmac.compare_digest(session["csrf_token"], supplied))


auth_store = AuthStore(Path(settings.data_dir) / "auth_runtime.sqlite3")
