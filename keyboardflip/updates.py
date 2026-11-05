"""Optional update check (off by default).

It asks GitHub for the number of the latest release and nothing else: no id, no
usage data. It never downloads or installs anything; it only tells you a newer
version exists and opens the download page when you ask.
"""
import json
import re
import urllib.request

from .config import REPO, VERSION

API_URL = "https://api.github.com/repos/%s/releases/latest" % REPO


def parse_version(text):
    """'v1.2.3' -> (1, 2, 3); None if it doesn't look like a version."""
    match = re.match(r"^\s*v?(\d+)\.(\d+)(?:\.(\d+))?", str(text))
    return tuple(int(p or 0) for p in match.groups()) if match else None


def is_newer(latest, current=VERSION):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def check_latest(timeout=6):
    """Return (latest_version_text, page_url), or None if it couldn't be checked."""
    try:
        request = urllib.request.Request(API_URL, headers={
            "User-Agent": "KeyboardFlip/" + VERSION, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        tag = str(data.get("tag_name", "")).strip()
        if not parse_version(tag):
            return None
        return tag.lstrip("vV"), str(data.get("html_url") or "")
    except Exception:
        return None
