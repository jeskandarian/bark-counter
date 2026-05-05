import csv
import datetime
import io
import zoneinfo

from flask import Blueprint, current_app, jsonify, make_response, request, send_from_directory

from src.storage.db import get_connection
from src.storage.models import query_episodes, query_stats

bp = Blueprint("main", __name__)


def _conn():
    return get_connection(current_app.config["DB_PATH"])


@bp.route("/")
def dashboard():
    return current_app.send_static_file("dashboard.html")


@bp.route("/api/barks")
def api_barks():
    start = request.args.get("start", type=float)
    end   = request.args.get("end",   type=float)
    conn  = _conn()
    try:
        rows = query_episodes(conn, start=start, end=end)
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/export.csv")
def api_export():
    start   = request.args.get("start", type=float)
    end     = request.args.get("end",   type=float)
    tz_name = request.args.get("tz", "UTC")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    conn = _conn()
    try:
        rows = query_episodes(conn, start=start, end=end)
    finally:
        conn.close()

    def fmt(ts):
        return datetime.datetime.fromtimestamp(ts, tz=tz).isoformat()

    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(["id","started_at_local","ended_at_local","duration_ms",
                "bark_count","peak_db","avg_db","confidence","wav_file"])
    for r in rows:
        w.writerow([r["id"], fmt(r["started_at"]), fmt(r["ended_at"]),
                    r["duration_ms"], r["bark_count"], r["peak_db"],
                    r["avg_db"], r["confidence"], r["wav_file"] or ""])

    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"]        = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=bark_export.csv"
    return resp


@bp.route("/recordings/<string:filename>")
def recordings(filename):
    return send_from_directory(current_app.config["RECORDINGS_DIR"], filename, conditional=True)


@bp.route("/api/stats")
def api_stats():
    conn  = _conn()
    try:
        stats = query_stats(conn)
    finally:
        conn.close()
    return jsonify(stats)
