import sqlite3
import json
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Base directory for database file
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "netmoni.db")

def init_db():
    """Initialize database tables with WAL mode for safe concurrency."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")

        # Table: reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                node_ip TEXT NOT NULL DEFAULT '0.0.0.0',
                timestamp TEXT NOT NULL,
                attack_detected INTEGER NOT NULL,
                attack_type TEXT,
                confidence REAL,
                summary TEXT,
                metrics_summary TEXT,
                anomalies_detected TEXT,
                potential_causes TEXT,
                recommended_actions TEXT,
                further_investigation TEXT,
                raw_data TEXT
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_node_ip ON reports(node_ip);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(timestamp);")

        # Table: node_statuses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS node_statuses (
                node_ip TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                attack_detected INTEGER NOT NULL,
                attack_type TEXT,
                confidence REAL,
                anomalies_detected TEXT,
                summary TEXT,
                role TEXT,
                last_updated TEXT NOT NULL,
                first_detected TEXT
            );
        """)

        # Table: network_metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                bytes_sent INTEGER,
                bytes_recv INTEGER,
                throughput_sent REAL,
                throughput_recv REAL,
                avg_latency REAL,
                avg_loss REAL,
                local_latency REAL,
                anomaly_detected INTEGER,
                attack_detected INTEGER
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON network_metrics(timestamp);")

        # Table: app_settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        conn.commit()
        logger.info(f"Database initialized successfully at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()

def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row factory enabled."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

# --- Reports Operations ---

def save_report(report_data: Dict[str, Any]) -> str:
    """Save or update an incident report."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        report_id = report_data.get("report_id") or report_data.get("id") or f"NR-{int(datetime.now().timestamp())}"
        node_ip = report_data.get("node_ip") or "0.0.0.0"  # Safe default to avoid NOT NULL violation
        timestamp = report_data.get("timestamp", datetime.now().isoformat())
        attack_detected = 1 if report_data.get("attack_detected") else 0
        attack_type = report_data.get("attack_type")
        confidence = float(report_data.get("confidence", 0.0) or 0.0)
        summary = report_data.get("summary", "")
        metrics_summary = str(report_data.get("metrics_summary", ""))
        anomalies = str(report_data.get("anomalies_detected", ""))
        causes = str(report_data.get("potential_causes", ""))
        actions = str(report_data.get("recommended_actions", ""))
        further = str(report_data.get("further_investigation", ""))
        raw_json = json.dumps(report_data)

        cursor.execute("""
            INSERT OR REPLACE INTO reports (
                id, node_ip, timestamp, attack_detected, attack_type, confidence,
                summary, metrics_summary, anomalies_detected, potential_causes,
                recommended_actions, further_investigation, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id, node_ip, timestamp, attack_detected, attack_type, confidence,
            summary, metrics_summary, anomalies, causes, actions, further, raw_json
        ))
        conn.commit()
        return report_id
    finally:
        conn.close()

def get_reports(limit: int = 50, node_ip: Optional[str] = None, attack_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve reports with optional filtering."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM reports WHERE 1=1"
        params = []
        if node_ip:
            query += " AND node_ip = ?"
            params.append(node_ip)
        if attack_type:
            query += " AND attack_type = ?"
            params.append(attack_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["attack_detected"] = bool(item["attack_detected"])
            if item.get("raw_data"):
                try:
                    item["raw_data"] = json.loads(item["raw_data"])
                except Exception:
                    pass
            results.append(item)
        return results
    finally:
        conn.close()

# --- Node Statuses Operations ---

def upsert_node_status(node_ip: str, data: Dict[str, Any]):
    """Insert or update node status in Central Controller."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()
        attack_detected = 1 if data.get("attack_detected") else 0
        attack_type = data.get("attack_type")
        confidence = float(data.get("confidence", 0.0) or 0.0)
        anomalies = str(data.get("anomalies_detected", ""))
        summary = str(data.get("summary", ""))
        role = data.get("role", "attacker" if attack_detected and "scan" in str(attack_type).lower() else "victim" if attack_detected else "benign")
        status = "Under Attack" if attack_detected else "Normal"

        cursor.execute("""
            INSERT INTO node_statuses (
                node_ip, status, attack_detected, attack_type, confidence,
                anomalies_detected, summary, role, last_updated, first_detected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_ip) DO UPDATE SET
                status=excluded.status,
                attack_detected=excluded.attack_detected,
                attack_type=excluded.attack_type,
                confidence=excluded.confidence,
                anomalies_detected=excluded.anomalies_detected,
                summary=excluded.summary,
                role=excluded.role,
                last_updated=excluded.last_updated
        """, (
            node_ip, status, attack_detected, attack_type, confidence,
            anomalies, summary, role, now_str, now_str
        ))
        conn.commit()
    finally:
        conn.close()

def get_all_node_statuses() -> Dict[str, Any]:
    """Get dictionary of all node statuses keyed by node_ip."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM node_statuses ORDER BY last_updated DESC")
        rows = cursor.fetchall()
        res = {}
        for r in rows:
            d = dict(r)
            d["attack_detected"] = bool(d["attack_detected"])
            res[d["node_ip"]] = d
        return res
    finally:
        conn.close()

def clear_simulation_data() -> Dict[str, int]:
    """Clear all node statuses and reports from the database (for simulation reset)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM node_statuses")
        deleted_statuses = cursor.rowcount
        cursor.execute("DELETE FROM reports")
        deleted_reports = cursor.rowcount
        conn.commit()
        logger.info(f"Simulation reset: cleared {deleted_statuses} node statuses and {deleted_reports} reports.")
        return {"deleted_statuses": deleted_statuses, "deleted_reports": deleted_reports}
    finally:
        conn.close()

# --- Metrics Operations ---

def save_metric(data: Dict[str, Any]):
    """Save real-time metric point to database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO network_metrics (
                timestamp, bytes_sent, bytes_recv, throughput_sent, throughput_recv,
                avg_latency, avg_loss, local_latency, anomaly_detected, attack_detected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(data.get("timestamp", datetime.now().isoformat())),
            data.get("bytes_sent", 0),
            data.get("bytes_recv", 0),
            data.get("throughput_sent", 0.0),
            data.get("throughput_recv", 0.0),
            data.get("avg_latency"),
            data.get("avg_loss"),
            data.get("local_latency"),
            1 if data.get("anomaly_detected") else 0,
            1 if data.get("attack_detected") else 0
        ))
        conn.commit()
    finally:
        conn.close()

def get_recent_metrics(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve recent network metrics."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM network_metrics ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()

# --- Settings Storage Operations ---

def get_setting(key: str, default: Any = None) -> Any:
    """Retrieve setting value by key."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["value_json"])
        return default
    finally:
        conn.close()

def save_setting(key: str, value: Any):
    """Save setting value as JSON."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()

# Auto-initialize DB on import
init_db()
