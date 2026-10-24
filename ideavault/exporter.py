"""Export ideas to JSON / Markdown and re-import JSON backups."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import APP_NAME, APP_VERSION, CATEGORIES, DEFAULT_CATEGORY
from .database import Idea, IdeaRepository, utc_now
from .utils import format_timestamp


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _unique(path: Path) -> Path:
    n, candidate = 1, path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        n += 1
    return candidate


def export_json(ideas: list[Idea], folder: str | Path) -> Path:
    path = _unique(Path(folder) / f"ideavault_export_{_stamp()}.json")
    payload = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "exported_at": utc_now(),
        "count": len(ideas),
        "ideas": [i.to_dict() for i in ideas],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_markdown(ideas: list[Idea], folder: str | Path) -> Path:
    path = _unique(Path(folder) / f"ideavault_export_{_stamp()}.md")
    lines = [f"# {APP_NAME} export", "",
             f"_Exported {datetime.now().strftime('%d %b %Y, %H:%M')} · {len(ideas)} ideas_", ""]
    ordered = CATEGORIES + sorted({i.category for i in ideas} - set(CATEGORIES))
    for cat in ordered:
        group = [i for i in ideas if i.category == cat]
        if not group:
            continue
        lines += [f"## {cat}", ""]
        for idea in group:
            lines.append(f"### {idea.display_title}")
            meta = f"Created {format_timestamp(idea.created_at)} · Updated {format_timestamp(idea.updated_at)}"
            if idea.tag_list:
                meta += " · Tags: " + " ".join(f"`#{t}`" for t in idea.tag_list)
            lines += [f"_{meta}_", ""]
            if idea.content.strip():
                lines += [idea.content.rstrip(), ""]
            lines += ["---", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def import_json(repo: IdeaRepository, file_path: str | Path) -> tuple[int, int]:
    """Import a file produced by export_json. Returns (imported, skipped_duplicates)."""
    data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    items = data.get("ideas") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("This file doesn't look like an IdeaVault JSON export.")

    existing = {(i.title, i.content, i.created_at) for i in repo.all_ideas()}
    fresh, skipped = [], 0
    for item in items:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags", "")
        if isinstance(tags, list):
            tags = ", ".join(map(str, tags))
        record = {
            "title": str(item.get("title", "")),
            "content": str(item.get("content", "")),
            "category": item.get("category") if item.get("category") in CATEGORIES else DEFAULT_CATEGORY,
            "tags": str(tags),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }
        key = (record["title"], record["content"], record["created_at"])
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        fresh.append(record)
    return repo.insert_many(fresh), skipped
