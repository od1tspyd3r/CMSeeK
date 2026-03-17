#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import cmseekdb.basic as cmseek


def _db_path() -> str:
    base = cmseek.access_directory if getattr(cmseek, "access_directory", "") else os.getcwd()
    return os.path.join(base, "cmseek_webui.sqlite3")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at INTEGER NOT NULL,
              target TEXT NOT NULL,
              target_norm TEXT NOT NULL,
              options_json TEXT NOT NULL,
              status TEXT NOT NULL,
              exit_code INTEGER,
              stdout TEXT NOT NULL,
              result_json TEXT
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_scans_target_norm_created ON scans(target_norm, created_at)")


def normalize_target(target: str) -> str:
    t = (target or "").strip().lower()
    if t.endswith("/"):
        t = t[:-1]
    t = t.replace("http://", "").replace("https://", "")
    return t


def create_scan(target: str, options: Dict[str, Any]) -> int:
    now = int(time.time())
    row = {
        "created_at": now,
        "target": target,
        "target_norm": normalize_target(target),
        "options_json": json.dumps(options, sort_keys=True),
        "status": "running",
        "exit_code": None,
        "stdout": "",
        "result_json": None,
    }
    with connect() as con:
        cur = con.execute(
            """
            INSERT INTO scans(created_at, target, target_norm, options_json, status, exit_code, stdout, result_json)
            VALUES (:created_at, :target, :target_norm, :options_json, :status, :exit_code, :stdout, :result_json)
            """,
            row,
        )
        return int(cur.lastrowid)


def append_stdout(scan_id: int, chunk: str) -> None:
    if not chunk:
        return
    with connect() as con:
        con.execute(
            "UPDATE scans SET stdout = stdout || ? WHERE id = ?",
            (chunk, scan_id),
        )


def finish_scan(scan_id: int, exit_code: int, status: str, result: Optional[Dict[str, Any]]) -> None:
    result_json = json.dumps(result, sort_keys=True, indent=2) if isinstance(result, dict) else None
    with connect() as con:
        con.execute(
            "UPDATE scans SET status = ?, exit_code = ?, result_json = ? WHERE id = ?",
            (status, int(exit_code), result_json, scan_id),
        )


def get_scan(scan_id: int) -> Optional[sqlite3.Row]:
    with connect() as con:
        cur = con.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
        return cur.fetchone()


def list_scans(limit: int = 50) -> List[sqlite3.Row]:
    with connect() as con:
        cur = con.execute("SELECT * FROM scans ORDER BY created_at DESC LIMIT ?", (int(limit),))
        return list(cur.fetchall())


def get_latest_two_for_target(target: str) -> Tuple[Optional[sqlite3.Row], Optional[sqlite3.Row]]:
    tn = normalize_target(target)
    with connect() as con:
        cur = con.execute(
            """
            SELECT * FROM scans
            WHERE target_norm = ? AND status = 'finished' AND result_json IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 2
            """,
            (tn,),
        )
        rows = list(cur.fetchall())
        newest = rows[0] if len(rows) > 0 else None
        prev = rows[1] if len(rows) > 1 else None
        return newest, prev

