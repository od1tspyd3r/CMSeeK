#!/usr/bin/python3
# -*- coding: utf-8 -*-
# This is a part of CMSeeK, check the LICENSE file for more information
#
# WPScan-backed plugin/theme enumeration (optional, off by default).

import json
import os
import subprocess
from typing import Any, Dict, List, Tuple

import cmseekdb.basic as cmseek


def _build_cmd(url: str) -> List[str]:
    cmd = ["wpscan", "--url", url, "--enumerate", "ap,at", "--format", "json"]
    api_token = os.environ.get("WPSCAN_API_TOKEN") or os.environ.get("WP_SCAN_API_TOKEN")
    if api_token:
        cmd.extend(["--api-token", api_token])
    return cmd


def start(url: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Run WPScan against the given URL and return (plugins, themes) lists.
    Each entry is a small dict (name, version?, statuses?, slug, etc.).
    """
    try:
        cmd = _build_cmd(url)
        cmseek.info("Running WPScan for active plugin/theme enumeration")
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=900,
        )
    except FileNotFoundError:
        cmseek.warning("WPScan not found in PATH; skipping WPScan enumeration")
        return [], []
    except subprocess.TimeoutExpired:
        cmseek.error("WPScan timed out; skipping WPScan enumeration")
        return [], []

    if proc.returncode not in (0, 1):
        cmseek.error("WPScan failed (exit code {0}), stderr: {1}".format(proc.returncode, proc.stderr.strip()))
        return [], []

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        cmseek.error("Failed to parse WPScan JSON output: {0}".format(e))
        return [], []

    plugins: List[Dict[str, Any]] = []
    themes: List[Dict[str, Any]] = []

    # WPScan JSON structure may evolve; handle defensively.
    wp_plugins = data.get("plugins", {}) or {}
    for slug, info in wp_plugins.items():
        if not isinstance(info, dict):
            continue
        p: Dict[str, Any] = {
            "name": slug,
            "slug": slug,
        }
        version = info.get("version")
        if version:
            p["version"] = version
        # mark vulnerability summary if present
        if info.get("vulnerabilities"):
            p["has_vulnerabilities"] = True
            p["vulnerability_count"] = len(info["vulnerabilities"])
        plugins.append(p)

    wp_themes = data.get("themes", {}) or {}
    for slug, info in wp_themes.items():
        if not isinstance(info, dict):
            continue
        t: Dict[str, Any] = {
            "name": slug,
            "slug": slug,
        }
        version = info.get("version")
        if version:
            t["version"] = version
        if info.get("vulnerabilities"):
            t["has_vulnerabilities"] = True
            t["vulnerability_count"] = len(info["vulnerabilities"])
        themes.append(t)

    # Sort for stable diffs
    plugins.sort(key=lambda x: x.get("name", ""))
    themes.sort(key=lambda x: x.get("name", ""))
    return plugins, themes

