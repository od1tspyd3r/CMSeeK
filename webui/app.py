#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from flask import Flask, abort, redirect, render_template, request, url_for

import cmseekdb.basic as cmseek
from webui import db
from webui.diff import diff_json, summarize_diff


def _cmseek_root() -> str:
    return os.path.dirname(os.path.abspath(__file__)).replace("webui", "")[:-1]


def _cmseek_result_dir_for_target(target: str) -> str:
    # Mirror `cmseekdb.basic.init_result_dir()` naming so we can reliably read the right cms.json.
    t = (target or "").strip()
    if "http://" in t:
        t = t.replace("http://", "")
    elif "https://" in t:
        t = t.replace("https://", "")
    if t.endswith("/"):
        t = t[:-1]
    for ch in ["/", "!", "?", "#", "@", "&", "%", "\\", "*", ":"]:
        t = t.replace(ch, "_")
    base = cmseek.access_directory if getattr(cmseek, "access_directory", "") else os.getcwd()
    return os.path.join(base, "Result", t)


def _result_json_for_target(target: str) -> Optional[Dict[str, Any]]:
    cms_json = os.path.join(_cmseek_result_dir_for_target(target), "cms.json")
    if not os.path.isfile(cms_json):
        return None
    try:
        with open(cms_json, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def _build_cmd(target: str, opts: Dict[str, Any]) -> list[str]:
    cmd = ["python3", "cmseek.py", "-u", target]
    if opts.get("random_agent"):
        cmd.append("--random-agent")
    if opts.get("googlebot"):
        cmd.append("--googlebot")
    if opts.get("follow_redirect"):
        cmd.append("--follow-redirect")
    if opts.get("no_redirect"):
        cmd.append("--no-redirect")
    if opts.get("light_scan"):
        cmd.append("--light-scan")
    if opts.get("only_cms"):
        cmd.append("--only-cms")
    if opts.get("strict_cms"):
        cmd.extend(["--strict-cms", str(opts["strict_cms"])])
    if opts.get("ignore_cms"):
        cmd.extend(["--ignore-cms", str(opts["ignore_cms"])])
    if opts.get("user_agent"):
        cmd.extend(["--user-agent", str(opts["user_agent"])])
    if opts.get("batch"):
        cmd.append("--batch")
    return cmd


def _validate_target(t: str) -> str:
    t = (t or "").strip()
    if not t:
        raise ValueError("Target is required")
    # CMSeeK accepts URLs without scheme but adds http://; for the web UI, require scheme for clarity.
    if "://" not in t:
        raise ValueError("Target must include scheme (http:// or https://)")
    return t


def run_scan_async(scan_id: int, target: str, opts: Dict[str, Any]) -> None:
    cmd = _build_cmd(target, opts)
    start = time.time()
    db.append_stdout(scan_id, f"$ {' '.join(cmd)}\n\n")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=_cmseek_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            db.append_stdout(scan_id, line)
        exit_code = proc.wait()
    except Exception as e:
        db.append_stdout(scan_id, f"\n[webui] Failed to run scan: {e}\n")
        db.finish_scan(scan_id, exit_code=1, status="failed", result=None)
        return

    elapsed = round(time.time() - start, 2)
    db.append_stdout(scan_id, f"\n[webui] Scan finished in {elapsed}s (exit={exit_code})\n")

    result = _result_json_for_target(target)
    if isinstance(result, dict):
        status = "finished"
    else:
        status = "failed"
    db.finish_scan(scan_id, exit_code=exit_code, status=status, result=result)


def create_app() -> Flask:
    app = Flask(__name__)
    # This is a local dev UI; auto-reload templates for faster iteration.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    db.init_db()

    @app.get("/")
    def index():
        scans = db.list_scans(limit=25)
        return render_template("index.html", scans=scans)

    @app.post("/scan")
    def start_scan():
        try:
            target = _validate_target(request.form.get("target", ""))
        except ValueError as e:
            abort(400, str(e))

        opts: Dict[str, Any] = {
            "random_agent": bool(request.form.get("random_agent")),
            "googlebot": bool(request.form.get("googlebot")),
            "follow_redirect": bool(request.form.get("follow_redirect")),
            "no_redirect": bool(request.form.get("no_redirect")),
            "light_scan": bool(request.form.get("light_scan")),
            "only_cms": bool(request.form.get("only_cms")),
            "strict_cms": (request.form.get("strict_cms") or "").strip(),
            "ignore_cms": (request.form.get("ignore_cms") or "").strip(),
            "user_agent": (request.form.get("user_agent") or "").strip(),
            "batch": True,
        }
        # Clean empty strings to keep options_json stable
        opts = {k: v for k, v in opts.items() if v not in ("", None, False)}

        scan_id = db.create_scan(target, opts)
        th = threading.Thread(target=run_scan_async, args=(scan_id, target, opts), daemon=True)
        th.start()
        return redirect(url_for("scan_detail", scan_id=scan_id))

    @app.get("/scans/<int:scan_id>")
    def scan_detail(scan_id: int):
        row = db.get_scan(scan_id)
        if not row:
            abort(404)
        result_obj = None
        if row["result_json"]:
            try:
                result_obj = json.loads(row["result_json"])
            except Exception:
                result_obj = None

        newest, prev = db.get_latest_two_for_target(row["target"])
        diff_items = []
        diff_summary = None
        if newest and prev and newest["id"] == row["id"]:
            try:
                new_obj = json.loads(newest["result_json"]) if newest["result_json"] else None
                old_obj = json.loads(prev["result_json"]) if prev["result_json"] else None
                if isinstance(new_obj, dict) and isinstance(old_obj, dict):
                    diff_items = diff_json(old_obj, new_obj)
                    diff_summary = summarize_diff(diff_items)
            except Exception:
                diff_items = []
                diff_summary = None

        return render_template(
            "scan_detail.html",
            scan=row,
            result_obj=result_obj,
            newest=newest,
            prev=prev,
            diff_items=diff_items,
            diff_summary=diff_summary,
        )

    return app

