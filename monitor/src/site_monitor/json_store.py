"""JSON persistence for reports, delivery events, and monitor state."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .monitor_config import PROJECT_ROOT


DATA_DIR = PROJECT_ROOT / "data"


class JsonMonitorStore:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir

    def _read(self, filename: str) -> list[dict[str, Any]]:
        path = self.data_dir / filename
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _write(self, filename: str, documents: list[dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(documents, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _upsert(self, filename: str, key: str, documents: list[dict[str, Any]]) -> int:
        current = self._read(filename)
        indexed = {item.get(key): item for item in current}
        for item in documents:
            indexed[item[key]] = item
        self._write(filename, list(indexed.values()))
        return len(documents)

    def record_delivery_events(self, events: list[dict[str, Any]]) -> int:
        return self._upsert(
            "delivery_events.json",
            "event_id",
            [dict(event) for event in events if event.get("event_id")],
        )

    def upsert_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        report_id = payload["report_id"]
        items = payload.get("items", [])
        content_count = sum(len(item.get("entries") or []) for item in items)
        report = {
            "report_id": report_id,
            "date": payload.get("date"),
            "title": payload.get("title"),
            "full_text": payload.get("full_text"),
            "generated_at": payload.get("generated_at"),
            "topics": payload.get("topics", []),
            "ai_enrichment": payload.get("ai_enrichment", {}),
            "item_count": len(items),
            "content_count": content_count,
            "content_item_count": sum(bool(item.get("entries")) for item in items),
            "updated_at": now,
        }
        report.setdefault("created_at", now)
        self._upsert("reports.json", "report_id", [report])
        stored_items = []
        for item in items:
            doc = dict(item)
            doc["entry_count"] = len(doc.get("entries") or [])
            doc.setdefault("report_id", report_id)
            doc.setdefault("item_id", f"{report_id}:{doc.get('topic')}")
            doc.setdefault("created_at", now)
            stored_items.append(doc)
            if item.get("topic") == "github_trending":
                self.upsert_project_intros(item.get("entries") or [], now=now)
        self._upsert("report_items.json", "item_id", stored_items)
        return {"report_id": report_id, "item_count": len(items)}

    def upsert_project_intros(
        self, entries: list[dict[str, Any]], *, now: str | None = None
    ) -> int:
        now = now or datetime.now().isoformat(timespec="seconds")
        documents = []
        for entry in entries:
            intro = entry.get("project_intro")
            full_name = str(entry.get("full_name") or "").strip()
            if not isinstance(intro, dict) or not intro or "/" not in full_name:
                continue
            doc = dict(intro)
            doc.update(
                full_name=full_name,
                slug=full_name.lower(),
                intro_url=entry.get("intro_url"),
                source_url=entry.get("source_url"),
                updated_at=now,
            )
            doc.setdefault("created_at", now)
            documents.append(doc)
        return self._upsert("project_intros.json", "slug", documents)

    def restore_monitor_state(self, state_dir: Path) -> int:
        state_dir.mkdir(parents=True, exist_ok=True)
        restored = 0
        for doc in self._read("monitor_state.json"):
            filename = doc.get("filename", "")
            if Path(filename).name != filename or not filename.endswith(".json"):
                continue
            (state_dir / filename).write_text(
                json.dumps(doc.get("data", {}), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            restored += 1
        return restored

    def save_monitor_state(self, state_dir: Path) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        docs = {item.get("filename"): item for item in self._read("monitor_state.json")}
        saved = 0
        for path in sorted(state_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            previous = docs.get(path.name, {})
            docs[path.name] = {
                **previous,
                "filename": path.name,
                "data": data,
                "created_at": previous.get("created_at", now),
                "updated_at": now,
            }
            saved += 1
        self._write("monitor_state.json", list(docs.values()))
        return saved


def create_store(*_args: Any, **_kwargs: Any) -> JsonMonitorStore:
    return JsonMonitorStore()
