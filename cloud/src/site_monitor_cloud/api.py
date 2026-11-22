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


class JsonReportStore:
    """Read report history from the committed MongoDB JSON export."""

    def __init__(self, archive_dir: Path | None = None):
        self.archive_dir = archive_dir or (
            Path(__file__).resolve().parents[3]
            / "monitor"
            / "data"
            / ""
        )

    def _read(self, filename: str) -> list[dict[str, Any]]:
        import json

        path = self.archive_dir / filename
        try:
            documents = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        for document in documents:
            document.pop("_id", None)
        return documents

    def project_intro(self, owner: str, repo: str) -> dict[str, Any] | None:
        slug = f"{owner}/{repo}".lower()
        return next(
            (item for item in self._read("project_intros.json") if item.get("slug") == slug),
            None,
        )

    def latest(self) -> dict[str, Any] | None:
        reports = sorted(
            self._read("reports.json"),
            key=lambda item: (
                item.get("date", ""),
                item.get("content_count", 0),
                item.get("generated_at", ""),
                item.get("updated_at", ""),
            ),
            reverse=True,
        )
        if not reports:
            return None
        return self.detail(reports[0]["report_id"])

    def list_reports(self, *, limit: int = 30, topic: str | None = None) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 100)
        if topic:
            documents = [item for item in self._read("report_items.json") if item.get("topic") == topic]
            documents.sort(
                key=lambda item: (
                    item.get("date", ""),
                    item.get("entry_count", 0),
                    item.get("created_at", ""),
                    item.get("item_id", ""),
                ),
                reverse=True,
            )
        else:
            documents = self._read("reports.json")
            documents.sort(
                key=lambda item: (
                    item.get("date", ""),
                    item.get("content_count", 0),
                    item.get("generated_at", ""),
                    item.get("updated_at", ""),
                    item.get("report_id", ""),
                ),
                reverse=True,
            )
        return newest_per_date(documents, limit=limit)

    def detail(self, report_id: str) -> dict[str, Any] | None:
        report = next(
            (item for item in self._read("reports.json") if item.get("report_id") == report_id),
            None,
        )
        if report is None:
            return None
        report["items"] = sorted(
            (item for item in self._read("report_items.json") if item.get("report_id") == report_id),
            key=lambda item: item.get("order", 0),
        )
        return report

    def topics(self) -> list[dict[str, Any]]:
        reports = sorted(self._read("reports.json"), key=lambda item: item.get("date", ""), reverse=True)
        return reports[0].get("topics", []) if reports else []


def create_store() -> JsonReportStore:
    return JsonReportStore()


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
        return jsonify({"error": "report_archive_is_read_only"}), 409

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
