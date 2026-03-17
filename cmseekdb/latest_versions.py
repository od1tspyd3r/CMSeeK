#!/usr/bin/python3
# -*- coding: utf-8 -*-
# This is a part of CMSeeK, check the LICENSE file for more information
#
# Upstream "latest stable" version helpers for self-hosted CMSes.

import re
import xml.etree.ElementTree as ET

import cmseekdb.basic as cmseek


def _version_key(v: str):
    """
    Best-effort semantic-ish version sort key.
    Returns a tuple of ints; non-numeric parts are ignored.
    """
    if not v:
        return ()
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts)


def latest_drupal(ua: str) -> str:
    """
    Returns latest stable Drupal core version string, or '0' on failure.
    Source: Drupal update/release-history feed.
    """
    src = cmseek.getsource("https://updates.drupal.org/release-history/drupal/current", ua)
    if src[0] != "1" or not src[1]:
        return "0"
    try:
        root = ET.fromstring(src[1])
        # Feed tends to be ordered newest-first, but we still choose max() safely.
        versions = []
        for rel in root.findall(".//release"):
            v = rel.findtext("version") or ""
            v = v.strip()
            if not v:
                continue
            # Skip dev/unstable markers when possible.
            if re.search(r"(dev|alpha|beta|rc)", v, re.IGNORECASE):
                continue
            versions.append(v)
        if not versions:
            return "0"
        return max(versions, key=_version_key)
    except Exception:
        return "0"


def latest_joomla(ua: str) -> str:
    """
    Returns latest stable Joomla core version string, or '0' on failure.
    Source: Joomla official update server list.
    """
    src = cmseek.getsource("https://update.joomla.org/core/list.xml", ua)
    if src[0] != "1" or not src[1]:
        return "0"
    try:
        root = ET.fromstring(src[1])
        versions = []
        for upd in root.findall(".//update"):
            v = (upd.findtext("version") or "").strip()
            if not v:
                continue
            if re.search(r"(dev|alpha|beta|rc)", v, re.IGNORECASE):
                continue
            versions.append(v)
        if not versions:
            return "0"
        return max(versions, key=_version_key)
    except Exception:
        return "0"

