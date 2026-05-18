"""Cloud API for the Android monitor app."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, request

from .report_payload import topics_payload


class MongoReportStore:
    def __init__(self, mongo_uri: str, db_name: str):
        from pymongo import MongoClient

        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.reports = self.db["reports"]
        self.items = self.db["report_items"]
        self.reports.create_index("date")
        self.items.create_index([("topic", 1), ("date", -1)])
        self.items.create_index("report_id")

    def upsert_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        report_id = payload["report_id"]
        items = payload.get("items", [])
        report_doc = {
            "report_id": report_id,
            "date": payload.get("date"),
            "title": payload.get("title"),
            "full_text": payload.get("full_text"),
            "generated_at": payload.get("generated_at"),
            "topics": payload.get("topics", topics_payload()),
            "item_count": len(items),
            "updated_at": now,
        }
        self.reports.update_one(
            {"report_id": report_id},
            {"$set": report_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        for item in items:
            item_doc = dict(item)
            item_doc.setdefault("report_id", report_id)
            item_doc.setdefault("item_id", f"{report_id}:{item_doc.get('topic')}")
            self.items.update_one(
                {"item_id": item_doc["item_id"]},
                {"$set": item_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        return {"report_id": report_id, "item_count": len(items)}

    def latest(self) -> dict[str, Any] | None:
        report = self.reports.find_one({}, {"_id": 0}, sort=[("date", -1), ("generated_at", -1)])
        if not report:
            return None
        report["items"] = list(
            self.items.find({"report_id": report["report_id"]}, {"_id": 0}).sort("order", 1)
        )
        return report

    def list_reports(self, *, limit: int = 30, topic: str | None = None) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 100)
        if topic:
            item_docs = list(
                self.items.find({"topic": topic}, {"_id": 0}).sort("date", -1).limit(limit)
            )
            return item_docs
        return list(
            self.reports.find({}, {"_id": 0, "full_text": 0}).sort("date", -1).limit(limit)
        )

    def detail(self, report_id: str) -> dict[str, Any] | None:
        report = self.reports.find_one({"report_id": report_id}, {"_id": 0})
        if not report:
            return None
        report["items"] = list(
            self.items.find({"report_id": report_id}, {"_id": 0}).sort("order", 1)
        )
        return report

    def topics(self) -> list[dict[str, Any]]:
        return topics_payload()


def create_store() -> MongoReportStore:
    mongo_uri = os.environ.get("SITE_MONITOR_MONGO_URI")
    db_name = os.environ.get("SITE_MONITOR_DB_NAME", "site_monitor")
    if not mongo_uri:
        raise RuntimeError("SITE_MONITOR_MONGO_URI is required")
    return MongoReportStore(mongo_uri, db_name)


def _require_header(header_name: str, expected: str | None) -> tuple[bool, Any]:
    if not expected:
        return False, (jsonify({"error": f"{header_name} is not configured"}), 500)
    if request.headers.get(header_name) != expected:
        return False, (jsonify({"error": "unauthorized"}), 401)
    return True, None


def create_app(store: Any | None = None) -> Flask:
    app = Flask(__name__)
    app.config["REPORT_STORE"] = store

    def get_store() -> Any:
        if app.config["REPORT_STORE"] is None:
            app.config["REPORT_STORE"] = create_store()
        return app.config["REPORT_STORE"]

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True})

    @app.post("/api/v1/reports")
    def upload_report():
        ok, response = _require_header(
            "X-Site-Monitor-Upload-Token",
            os.environ.get("SITE_MONITOR_UPLOAD_TOKEN"),
        )
        if not ok:
            return response
        payload = request.get_json(silent=True) or {}
        if not payload.get("report_id"):
            return jsonify({"error": "report_id is required"}), 400
        result = get_store().upsert_report(payload)
        return jsonify({"success": True, **result})

    @app.get("/api/v1/reports/latest")
    def latest_report():
        ok, response = _require_header(
            "X-Site-Monitor-App-Token",
            os.environ.get("SITE_MONITOR_APP_TOKEN"),
        )
        if not ok:
            return response
        report = get_store().latest()
        if report is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(report)

    @app.get("/api/v1/reports")
    def list_reports():
        ok, response = _require_header(
            "X-Site-Monitor-App-Token",
            os.environ.get("SITE_MONITOR_APP_TOKEN"),
        )
        if not ok:
            return response
        limit = request.args.get("limit", "30")
        try:
            limit_value = int(limit)
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
        return jsonify(
            {
                "items": get_store().list_reports(
                    limit=limit_value,
                    topic=request.args.get("topic") or None,
                )
            }
        )

    @app.get("/api/v1/reports/<report_id>")
    def report_detail(report_id: str):
        ok, response = _require_header(
            "X-Site-Monitor-App-Token",
            os.environ.get("SITE_MONITOR_APP_TOKEN"),
        )
        if not ok:
            return response
        report = get_store().detail(report_id)
        if report is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify(report)

    @app.get("/api/v1/topics")
    def topics():
        ok, response = _require_header(
            "X-Site-Monitor-App-Token",
            os.environ.get("SITE_MONITOR_APP_TOKEN"),
        )
        if not ok:
            return response
        return jsonify({"topics": get_store().topics()})

    return app


app = create_app()
