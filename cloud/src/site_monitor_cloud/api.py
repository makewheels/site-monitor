"""Cloud API for the Android monitor app."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from flask import Flask, Response, jsonify, request, send_from_directory

from .project_page import render_project_page


def newest_per_date(
    documents: Iterable[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Keep the preferred document for each date from an ordered cursor."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        identity = str(
            document.get("date")
            or document.get("report_id")
            or document.get("item_id")
            or ""
        )
        if identity in seen:
            continue
        seen.add(identity)
        results.append(document)
        if len(results) >= limit:
            break
    return results


class MongoReportStore:
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
        self.project_intros = self.db["project_intros"]
        self.reports.create_index(
            [("date", -1), ("content_count", -1), ("generated_at", -1)]
        )
        self.items.create_index(
            [("topic", 1), ("date", -1), ("entry_count", -1)]
        )
        self.items.create_index("report_id")
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

    def project_intro(self, owner: str, repo: str) -> dict[str, Any] | None:
        return self.project_intros.find_one(
            {"slug": f"{owner}/{repo}".lower()},
            {"_id": 0},
        )

    def latest(self) -> dict[str, Any] | None:
        report = self.reports.find_one(
            {},
            {"_id": 0},
            sort=[
                ("date", -1),
                ("content_count", -1),
                ("generated_at", -1),
                ("updated_at", -1),
            ],
        )
        if not report:
            return None
        report["items"] = list(
            self.items.find({"report_id": report["report_id"]}, {"_id": 0}).sort("order", 1)
        )
        return report

    def list_reports(self, *, limit: int = 30, topic: str | None = None) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 100)
        if topic:
            item_docs = self.items.find({"topic": topic}, {"_id": 0}).sort(
                [
                    ("date", -1),
                    ("entry_count", -1),
                    ("created_at", -1),
                    ("item_id", -1),
                ]
            )
            return newest_per_date(item_docs, limit=limit)
        report_docs = self.reports.find({}, {"_id": 0, "full_text": 0}).sort(
            [
                ("date", -1),
                ("content_count", -1),
                ("generated_at", -1),
                ("updated_at", -1),
                ("report_id", -1),
            ]
        )
        return newest_per_date(report_docs, limit=limit)

    def detail(self, report_id: str) -> dict[str, Any] | None:
        report = self.reports.find_one({"report_id": report_id}, {"_id": 0})
        if not report:
            return None
        report["items"] = list(
            self.items.find({"report_id": report_id}, {"_id": 0}).sort("order", 1)
        )
        return report

    def topics(self) -> list[dict[str, Any]]:
        report = self.reports.find_one({}, {"_id": 0, "topics": 1}, sort=[("date", -1)])
        return report.get("topics", []) if report else []


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


def app_release_payload() -> dict[str, Any] | None:
    version_code = os.environ.get("SITE_MONITOR_ANDROID_VERSION_CODE", "").strip()
    version_name = os.environ.get("SITE_MONITOR_ANDROID_VERSION_NAME", "").strip()
    apk_url = os.environ.get("SITE_MONITOR_ANDROID_APK_URL", "").strip()
    if not version_code or not version_name or not apk_url:
        return None
    try:
        parsed_version_code = int(version_code)
    except ValueError:
        return None
    return {
        "version_code": parsed_version_code,
        "version_name": version_name,
        "apk_url": apk_url,
        "sha256": os.environ.get("SITE_MONITOR_ANDROID_APK_SHA256", "").strip(),
        "release_notes": os.environ.get("SITE_MONITOR_ANDROID_RELEASE_NOTES", "").strip(),
        "force_update": os.environ.get("SITE_MONITOR_ANDROID_FORCE_UPDATE", "").lower()
        in {"1", "true", "yes"},
    }


def create_app(store: Any | None = None) -> Flask:
    app = Flask(__name__)
    app.config["REPORT_STORE"] = store
    web_dir = Path(__file__).with_name("web")

    @app.after_request
    def add_web_security_headers(response):
        if request.path == "/" or request.path.startswith("/web"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "style-src 'self'; "
                "script-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'"
            )
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/")
    @app.get("/web")
    @app.get("/web/")
    def web_app():
        response = send_from_directory(web_dir, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/web/assets/<path:filename>")
    def web_asset(filename: str):
        return send_from_directory(web_dir / "assets", filename)

    @app.get("/projects/<owner>/<repo>")
    def project_page(owner: str, repo: str):
        project = get_store().project_intro(owner, repo)
        if project is None:
            return Response("项目解读尚未生成", status=404, content_type="text/plain; charset=utf-8")
        response = Response(
            render_project_page(project),
            content_type="text/html; charset=utf-8",
        )
        response.headers["Cache-Control"] = "public, max-age=300"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

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

    @app.get("/api/v1/app/releases/latest")
    def latest_app_release():
        ok, response = _require_header(
            "X-Site-Monitor-App-Token",
            os.environ.get("SITE_MONITOR_APP_TOKEN"),
        )
        if not ok:
            return response
        release = app_release_payload()
        if release is None:
            return jsonify({"error": "not_configured"}), 404
        return jsonify(release)

    return app


app = create_app()
