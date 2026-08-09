"""MongoDB persistence for scheduled monitor reports and state."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class MongoMonitorStore:
    def __init__(self, mongo_uri: str, db_name: str):
        from pymongo import MongoClient

        self.client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=5_000,
        )
        self.db = self.client[db_name]
        self.reports = self.db["reports"]
        self.items = self.db["report_items"]
        self.monitor_state = self.db["monitor_state"]
        self.project_intros = self.db["project_intros"]
        self.reports.create_index(
            [("date", -1), ("content_count", -1), ("generated_at", -1)]
        )
        self.items.create_index(
            [("topic", 1), ("date", -1), ("entry_count", -1)]
        )
        self.items.create_index("report_id")
        self.monitor_state.create_index("filename", unique=True)
        self.project_intros.create_index("slug", unique=True)

    def upsert_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        report_id = payload["report_id"]
        items = payload.get("items", [])
        content_count = sum(len(item.get("entries") or []) for item in items)
        content_item_count = sum(1 for item in items if item.get("entries"))
        report_doc = {
            "report_id": report_id,
            "date": payload.get("date"),
            "title": payload.get("title"),
            "full_text": payload.get("full_text"),
            "generated_at": payload.get("generated_at"),
            "topics": payload.get("topics", []),
            "ai_enrichment": payload.get("ai_enrichment", {}),
            "item_count": len(items),
            "content_count": content_count,
            "content_item_count": content_item_count,
            "updated_at": now,
        }
        self.reports.update_one(
            {"report_id": report_id},
            {"$set": report_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        for item in items:
            item_doc = dict(item)
            item_doc["entry_count"] = len(item_doc.get("entries") or [])
            item_doc.setdefault("report_id", report_id)
            item_doc.setdefault("item_id", f"{report_id}:{item_doc.get('topic')}")
            created_at = item_doc.pop("created_at", now)
            self.items.update_one(
                {"item_id": item_doc["item_id"]},
                {"$set": item_doc, "$setOnInsert": {"created_at": created_at}},
                upsert=True,
            )
            if item.get("topic") == "github_trending":
                self.upsert_project_intros(item.get("entries") or [], now=now)
        return {"report_id": report_id, "item_count": len(items)}

    def upsert_project_intros(
        self,
        entries: list[dict[str, Any]],
        *,
        now: str | None = None,
    ) -> int:
        now = now or datetime.now().isoformat(timespec="seconds")
        saved = 0
        for entry in entries:
            intro = entry.get("project_intro")
            full_name = str(entry.get("full_name") or "").strip()
            if not isinstance(intro, dict) or not intro or "/" not in full_name:
                continue
            document = dict(intro)
            document["full_name"] = full_name
            document["slug"] = full_name.lower()
            document["intro_url"] = entry.get("intro_url")
            document["source_url"] = entry.get("source_url")
            document["updated_at"] = now
            self.project_intros.update_one(
                {"slug": document["slug"]},
                {"$set": document, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            saved += 1
        return saved

    def restore_monitor_state(self, state_dir: Path) -> int:
        state_dir.mkdir(parents=True, exist_ok=True)
        restored = 0
        for document in self.monitor_state.find({}, {"_id": 0}):
            filename = document.get("filename", "")
            if not filename.endswith(".json") or Path(filename).name != filename:
                continue
            (state_dir / filename).write_text(
                json.dumps(document.get("data", {}), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            restored += 1
        return restored

    def save_monitor_state(self, state_dir: Path) -> int:
        saved = 0
        now = datetime.now().isoformat(timespec="seconds")
        for path in sorted(state_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            self.monitor_state.update_one(
                {"filename": path.name},
                {
                    "$set": {"data": data, "updated_at": now},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            saved += 1
        return saved


def create_store(mongo_uri: str, db_name: str = "site_monitor") -> MongoMonitorStore:
    if not mongo_uri:
        raise RuntimeError("SITE_MONITOR_MONGO_URI is required")
    return MongoMonitorStore(mongo_uri, db_name)
