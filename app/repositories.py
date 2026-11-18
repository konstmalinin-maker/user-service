"""SQLite-репозиторий пользователей: отдельная БД, WAL и транзакции."""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.common_models import ConflictError, StorageError, utc_now


class UserRepository:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def create(self, email, name):
        try:
            with closing(self.connect()) as db, db:
                cursor = db.execute("INSERT INTO users(email,name,created_at) VALUES (?,?,?)", (email, name, utc_now()))
                return dict(db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Пользователь с таким email уже существует") from exc
        except sqlite3.Error as exc:
            raise StorageError("Не удалось сохранить пользователя") from exc

    def list_all(self):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute("SELECT * FROM users ORDER BY id")]

    def get(self, user_id):
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def update(self, user_id, email, name):
        try:
            with closing(self.connect()) as db, db:
                result = db.execute("UPDATE users SET email=?,name=? WHERE id=?", (email, name, user_id))
                if result.rowcount == 0:
                    return None
                return dict(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Пользователь с таким email уже существует") from exc

    def delete(self, user_id):
        with closing(self.connect()) as db, db:
            return db.execute("DELETE FROM users WHERE id=?", (user_id,)).rowcount > 0

    def ready(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT 1").fetchone()[0] == 1
