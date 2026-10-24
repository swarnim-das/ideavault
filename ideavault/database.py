"""SQLite persistence layer. All data stays in a single local file (ideas.db)."""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import DEFAULT_CATEGORY

SCHEMA_VERSION = 1
EDITABLE_FIELDS = ("title", "content", "category", "tags")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_tags(raw: str) -> str:
    """'ui,  Python, ui ,,#ux' -> 'ui, Python, ux' (trimmed, de-duplicated case-insensitively)."""
    seen: set[str] = set()
    out: list[str] = []
    for part in (raw or "").split(","):
        tag = part.strip().lstrip("#").strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return ", ".join(out)


@dataclass
class Idea:
    id: int
    title: str
    content: str
    category: str
    tags: str
    created_at: str
    updated_at: str

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def display_title(self) -> str:
        return self.title.strip() or "Untitled idea"

    def is_empty(self) -> bool:
        return not (self.title.strip() or self.content.strip() or self.tags.strip())

    def to_dict(self) -> dict:
        data = asdict(self)
        data["tag_list"] = self.tag_list
        return data


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class IdeaRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    # ------------------------------------------------------------------ schema
    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.conn.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS ideas (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL DEFAULT '',
                    content     TEXT NOT NULL DEFAULT '',
                    category    TEXT NOT NULL DEFAULT '{DEFAULT_CATEGORY}',
                    tags        TEXT NOT NULL DEFAULT '',
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ideas_category ON ideas(category);
                CREATE INDEX IF NOT EXISTS idx_ideas_updated  ON ideas(updated_at DESC);
                PRAGMA user_version = {SCHEMA_VERSION};
                """
            )
        # Future migrations: `if version < 2: ...` then bump SCHEMA_VERSION.

    # ------------------------------------------------------------------ reads
    @staticmethod
    def _row(row: sqlite3.Row | None) -> Idea | None:
        return Idea(**dict(row)) if row else None

    def get(self, idea_id: int) -> Idea | None:
        return self._row(self.conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone())

    def list_ideas(self, category: str | None = None, query: str = "", limit: int | None = None) -> list[Idea]:
        """Newest-edited first. Every search word must match title, content or tags.
        A word starting with '#' matches tags only (e.g. '#python')."""
        where, params = [], []
        if category:
            where.append("category = ?")
            params.append(category)
        for word in query.split():
            if word.startswith("#") and len(word) > 1:
                where.append("tags LIKE ? ESCAPE '\\'")
                params.append(f"%{_escape_like(word[1:])}%")
            else:
                like = f"%{_escape_like(word)}%"
                where.append("(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' OR tags LIKE ? ESCAPE '\\')")
                params += [like, like, like]
        sql = "SELECT * FROM ideas"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC, id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [Idea(**dict(r)) for r in self.conn.execute(sql, params)]

    def category_counts(self) -> dict[str, int]:
        counts = {r["category"]: r["n"] for r in
                  self.conn.execute("SELECT category, COUNT(*) AS n FROM ideas GROUP BY category")}
        counts["__total__"] = sum(counts.values())
        return counts

    def all_ideas(self) -> list[Idea]:
        return [Idea(**dict(r)) for r in self.conn.execute("SELECT * FROM ideas ORDER BY created_at, id")]

    # ------------------------------------------------------------------ writes
    def create(self, category: str = DEFAULT_CATEGORY, title: str = "", content: str = "", tags: str = "") -> Idea:
        now = utc_now()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO ideas (title, content, category, tags, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (title, content, category, normalize_tags(tags), now, now),
            )
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, idea_id: int, **fields) -> Idea | None:
        """Update editable fields. No-op (and no timestamp bump) when nothing changed."""
        current = self.get(idea_id)
        if current is None:
            return None
        changes = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
        if "tags" in changes:
            changes["tags"] = normalize_tags(changes["tags"])
        changes = {k: v for k, v in changes.items() if getattr(current, k) != v}
        if not changes:
            return current
        changes["updated_at"] = utc_now()
        cols = ", ".join(f"{k} = ?" for k in changes)
        with self.conn:
            self.conn.execute(f"UPDATE ideas SET {cols} WHERE id = ?", (*changes.values(), idea_id))
        return self.get(idea_id)

    def delete(self, idea_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))

    def insert_many(self, records: Iterable[dict]) -> int:
        """Insert records preserving their timestamps; used by JSON import."""
        rows = []
        for r in records:
            now = utc_now()
            rows.append((r.get("title", ""), r.get("content", ""), r.get("category", DEFAULT_CATEGORY),
                         normalize_tags(r.get("tags", "")), r.get("created_at") or now, r.get("updated_at") or now))
        with self.conn:
            self.conn.executemany(
                "INSERT INTO ideas (title, content, category, tags, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                rows,
            )
        return len(rows)

    # ------------------------------------------------------------------ maintenance
    def backup_to(self, dest: str | Path) -> Path:
        """Consistent copy of the live database using SQLite's online backup API."""
        dest = Path(dest)
        target = sqlite3.connect(str(dest))
        try:
            self.conn.backup(target)
        finally:
            target.close()
        return dest

    def close(self) -> None:
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        self.conn.close()
