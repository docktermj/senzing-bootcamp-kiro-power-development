#!/usr/bin/env python3
"""Capture one screenshot per tab of a bootcamp visualization, for the recap.

Best-effort and dependency-optional (INV-052/INV-066): this helper renders a
**local** HTML file (or a localhost URL served by the bundled visualization app)
to one PNG **per tab**, so the graduation recap PDF can show what the bootcamper
actually built. It tries several headless backends in order and uses the first
that works; if none is available it exits with code 2 so the caller degrades
gracefully — keeping the HTML link and never blocking graduation (INV-048).

⛔ **One capture per tab, never per viewport.** This script used to vary the
browser window size across a single page load — ``(1280,800)``, ``(1280,1600)``,
``(1024,768)`` — and had no interaction step at all, so every image showed
whichever tab was active by default. Three files were written, the script exited
0, and nothing looked wrong; the recap shipped three near-identical Entity Graph
shots with captions describing tabs that were never captured. Tab diversity was
not achievable, so the captions could not have been right.

Two consequences are designed in here:

* Output is named ``<name>-<tab-slug>.png``. A tab-named file makes a drifting
  caption structurally hard, and lets graduation's screenshot backfill map images
  to sections and tabs deterministically instead of by guesswork.
* Each written path is printed with its human tab label, tab-separated, so the
  caller derives the caption from the capture rather than from its plan.

How a tab is selected, without adding a browser-automation dependency:

* ``--url http://localhost:PORT`` — appended as ``?tab=<id>``, which the
  visualization app honors on load (``applyDeepLink``). ``--query`` adds ``&q=``
  so Search / Probe can be captured showing real results against the live engine.
* ``--html path/to/snapshot.html`` — a temp sibling copy is written with a small
  script injected before ``</body>`` that calls the app's own ``activate(<id>)``
  (falling back to clicking ``#navbtn-<id>``), retrying until the app's async
  init settles. Temp copies are always deleted.

Because selection happens *in the page*, every backend below works per tab —
including the ones with no interaction API.

Offline guarantee (INV-091): only local files and ``localhost``/``127.0.0.1``
URLs are ever opened. A non-local ``http(s)`` host is refused — this helper
never fetches from the network.

Backends tried, in order (each optional):
  1. Playwright (``playwright`` + a browser) — ``python3 -m pip install playwright``.
  2. Selenium (``selenium`` + a headless Chrome/Firefox driver).
  3. Headless Chrome/Chromium CLI (``--headless --screenshot``).
  4. ``wkhtmltoimage`` CLI.

Usage::

    # static snapshot, all applicable tabs
    python3 capture_screenshots.py --html docs/visualizations/foo.html \
        --out-dir docs/visualizations --name foo

    # live server, specific tabs, with a real search for Search / Probe
    python3 capture_screenshots.py --url http://localhost:8080 \
        --name results_visualization --tabs graph,stats,probe --query "Acme"

On success it prints one ``<png path>\\t<tab label>`` line per capture and exits 0.
Exit codes: 0 = wrote at least one PNG; 2 = no headless capability available
(caller should skip screenshots); 1 = bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlencode

# Sidecar manifest written beside the PNGs, recording what capture actually did.
#
# It exists because the recap PDF's `embedded N of M images` count derives its
# denominator from the very Markdown it is measuring: if only four of six tabs were
# ever captured, the line reads `embedded 4 of 4 images` — a perfect score against an
# incomplete set. Only capture knows how many tabs there were, and capture is
# best-effort and non-blocking by contract (INV-122), so the count it reached has to be
# recorded here or it is lost. `generate_recap_pdf.py --check` reads this to get an
# **external** denominator.
MANIFEST_SCHEMA = 1

# The visualization contract's tab inventory: id -> (filename slug, human label).
# Ids are the app's DOM ids (`tab-<id>`, `navbtn-<id>`) and are contract, not an
# implementation detail, so a server written in any language (INV-090) is capturable.
# The slug is what makes a caption hard to get wrong.
#
# ⛔ `network` and `merges` are RESERVED, not tabs to capture from a current app — a
# current server MUST NOT serve them, and DEFAULT_TABS excludes them. They stay here
# so this helper still names them correctly when pointed at a snapshot saved by an
# earlier eight-tab run, and so nothing reuses those ids for a different tab. Deleting
# them as "dead" silently re-slugs old snapshots to `<id>-<id>.png` (see _out_path's
# fallback) and breaks graduation's caption mapping.
TABS = {
    "graph": ("entity-graph", "Entity Graph"),
    "network": ("relationship-network", "Relationship Network"),
    "merges": ("record-merges", "Record Merges"),
    "stats": ("merge-statistics", "Merge Statistics"),
    "matchkeys": ("match-keys", "Match Keys"),
    "features": ("feature-scores", "Feature Scores"),
    "overlap": ("cross-source", "Cross-Source"),
    "probe": ("search-probe", "Search / Probe"),
}

# Captured when --tabs is not given. Ordered as the app presents them. A tab whose
# data is absent simply renders its empty state; the caller keeps what is useful.
DEFAULT_TABS = ("graph", "stats", "matchkeys", "features", "overlap", "probe")

# The RESERVED ids, split out from TABS so no user-visible string can enumerate them as
# live. `TABS` still accepts them (an old eight-tab snapshot must keep its slugs), but
# `--help` and the unknown-id error name the live six only — those strings are built at
# runtime and carry none of the framing the comment above TABS does, so a reader of
# `--help` was being shown eight capturable tabs for a six-tab app (INV-155).
RESERVED_TABS = tuple(t for t in TABS if t not in DEFAULT_TABS)

# ⛔ Not a tab: the internal id for capturing a page that HAS no tabs, as one image.
# It is deliberately absent from TABS, so `--tabs page` is an unknown id and the only
# way to reach this mode is `--single` (or the auto-detect safety net). A single-page
# deliverable — the quality and mapping pages — has no tab controls at all, so asking
# for "all tabs" against it requested six that do not exist and wrote **nothing**: an
# omitted `--tabs` never meant "no tabs", it meant DEFAULT_TABS. The concept was
# missing from this helper, not merely mis-invoked by its caller.
SINGLE_PAGE_ID = "page"
SINGLE_PAGE_LABEL = "Full page"

# ⛔ The label must describe what the capture DID, not what the mode intended (INV-235).
#
# `--single` inherited the tabbed path's fixed viewport, where the premise does not hold: a
# tab's content is designed to fit a screen, but a single-page deliverable is a *document*
# and is as tall as its content. So the mode cropped to 1440×900 and printed "Full page"
# regardless — and INV-123 names that printed label as the designated input to the caption a
# caller writes, so obeying INV-123 exactly produced "Full page" over the top third of a
# page. Only measuring the page's height against the PNG's revealed it, which nothing asked
# for. (Observed 2026-08-14: a three-source quality page ~2100px tall captured at 900px, two
# of three sources absent, exit 0, real 84 KB PNG, manifest entry, label "Full page".)
SINGLE_PAGE_LABEL_VIEWPORT = "Top of page (viewport only)"
FULL_PAGE_FULL = "full"
FULL_PAGE_CLAMPED = "clamped"
FULL_PAGE_VIEWPORT = "viewport"

# A pathological page must not produce a 30,000px PNG. When the clamp bites, the label and
# stderr both say so rather than truncating silently — the skip-and-report discipline
# INV-122 already requires of this script, applied to height.
_MAX_FULL_PAGE_PX = 12000


def _single_page_label(outcome: str, page_height=None, captured_height=None) -> str:
    """Label for a single-page capture, derived from what the backend actually did."""
    if outcome == FULL_PAGE_FULL:
        return SINGLE_PAGE_LABEL
    if outcome == FULL_PAGE_CLAMPED:
        return f"{SINGLE_PAGE_LABEL} (clamped at {_MAX_FULL_PAGE_PX}px)"
    return SINGLE_PAGE_LABEL_VIEWPORT


def _tab_label(tab: str) -> str:
    """Human label for a tab id, or for the single-page pseudo-id.

    For the single-page id the label depends on the capture's OUTCOME, which the backend
    records in `_FULL_PAGE_OUTCOME` — read here rather than threaded through, for the same
    reason `_CURRENT_TAB` is a global: `_BACKENDS` is called uniformly and tests substitute
    two-argument callables. See the note on `_CURRENT_TAB` for why serial capture makes that
    safe, and what to do if capture is ever parallelized.
    """
    if tab == SINGLE_PAGE_ID:
        return _single_page_label(
            _FULL_PAGE_OUTCOME, _FULL_PAGE_HEIGHT, _FULL_PAGE_CAPTURED
        )
    return TABS.get(tab, (tab, tab))[1]


def _has_tab_controls(source: str) -> bool:
    """Does this page have a tab bar at all?

    Used only to tell "a tabbed app whose tabs were misnamed" (report and skip — INV-122)
    from "a document that has no tabs by design" (capture it whole). An unreadable page
    returns False for both halves of the check, so the caller keeps its normal reporting
    path rather than guessing.
    """
    if not source:
        return False
    return bool(
        re.search(r'id\s*=\s*["\']navbtn-', source)
        or re.search(r'id\s*=\s*["\']tab-', source)
    )

# Chrome needs a virtual-time budget or the frame is captured before the D3 layout
# and the /api/* fetches settle — the difference between a graph and a blank panel.
_CHROME_VIRTUAL_TIME_MS = 15000

# Tabs whose content ANIMATES to its final position need longer than the static ones.
# This is settle time, not a timeout: the Entity Graph runs a d3 force simulation, and a
# capture taken before it spreads shows every node bunched in a corner — a valid PNG of a
# graph that looks like it found nothing. The static tabs (tables, histograms) are done as
# soon as their data lands, so raising the budget globally would slow every capture to pay
# for one tab.
_CHROME_VIRTUAL_TIME_MS_ANIMATED = 30000
_ANIMATED_TABS = frozenset({"graph", "network"})


def _virtual_time_ms(tab: str = "") -> int:
    """Virtual-time budget for ``tab`` — longer where the layout animates."""
    return (
        _CHROME_VIRTUAL_TIME_MS_ANIMATED
        if tab in _ANIMATED_TABS
        else _CHROME_VIRTUAL_TIME_MS
    )


_WINDOW = (1440, 900)

# Injected into a temp copy of a snapshot. Retries because the app activates its
# first tab only after an async init; 60 × 100 ms is far longer than that takes.
_ACTIVATE_JS = """
<script>
(function(){
  var target = "__TAB__", tries = 0;
  function go(){
    tries++;
    try {
      if (typeof activate === "function" && document.getElementById("tab-" + target)) {
        activate(target);
        return;
      }
      var btn = document.getElementById("navbtn-" + target);
      if (btn) { btn.click(); return; }
    } catch (e) { /* keep retrying */ }
    if (tries < 60) setTimeout(go, 100);
  }
  go();
})();
</script>
"""


_NON_LOCAL_TARGET = (
    "refusing non-local target {target!r}: only local files and "
    "localhost URLs are captured (offline guarantee, INV-091)"
)


def _is_local_target(target: str) -> bool:
    """True for a local file path or a localhost URL; False for a remote host."""
    parsed = urlparse(target)
    if parsed.scheme in ("", "file"):
        return True
    if parsed.scheme in ("http", "https"):
        host = (parsed.hostname or "").lower()
        return host in ("localhost", "127.0.0.1", "::1")
    return False


def _to_url(target: str) -> str:
    """Turn a local file path into a file:// URL; pass URLs through unchanged."""
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https", "file"):
        return target
    return Path(target).resolve().as_uri()


def _out_path(out_dir: Path, name: str, tab: str) -> Path:
    if tab == SINGLE_PAGE_ID:
        # No slug suffix: a single-page deliverable has one image, so `{name}.png` is
        # the predictable embed target beside the tabbed `{name}-<slug>.png` convention.
        return out_dir / f"{name}.png"
    slug = TABS.get(tab, (tab, tab))[0]
    return out_dir / f"{name}-{slug}.png"


def _tab_url(url: str, tab: str, query: str = "") -> str:
    """Append ?tab=/&q= deep-link parameters to a live-server URL."""
    params = {"tab": tab}
    if query and tab == "probe":
        params["q"] = query
    joiner = "&" if urlparse(url).query else "?"
    return f"{url}{joiner}{urlencode(params)}"


def _page_source(target: str, is_url: bool) -> str:
    """The page's HTML, for the tab-presence pre-flight. Empty string if unreadable.

    ⛔ The locality check is *outside* the ``try`` on purpose. Everything inside it
    degrades to ``""`` so an unreachable page never blocks graduation — but a non-local
    target must never reach ``urlopen`` at all, and swallowing that as "unreadable"
    would fetch it first and then hide the fact (offline guarantee, INV-091).
    """
    if is_url and not _is_local_target(target):
        raise ValueError(_NON_LOCAL_TARGET.format(target=target))
    try:
        if is_url:
            import urllib.request

            with urllib.request.urlopen(target, timeout=10) as response:
                return response.read().decode("utf-8", "replace")
        return Path(target).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _page_stats(source: str, target: str, is_url: bool) -> dict:
    """The page's ``/api/stats`` payload, or ``{}`` when it cannot be determined.

    Needed because a tab's *applicability* is a property of the data, not the markup:
    the app suppresses a tab whose data does not exist (see ``_tabs_applicable``), and
    the suppression happens at runtime in ``buildNav()``, so nothing in the saved markup
    records it.

    Two shapes, because the two targets carry stats differently:

    * a standalone snapshot inlines every endpoint as ``const __DATA__={...};`` (see
      ``senzing_viz_server.write_snapshot``), so ``stats`` is parsed straight out of it;
    * a live server serves ``/api/stats``, so it is fetched.

    ``{}`` on any failure — an unreadable or unrecognized page must never block capture
    (INV-122 is best-effort by contract), and an empty dict makes every tab applicable,
    which is exactly today's behavior.
    """
    marker = "const __DATA__="
    at = source.find(marker)
    if at != -1:
        try:
            data, _ = json.JSONDecoder().raw_decode(source, at + len(marker))
            stats = data.get("stats")
            return stats if isinstance(stats, dict) else {}
        except Exception:
            return {}
    if not is_url:
        return {}
    if not _is_local_target(target):  # never fetch a remote host (INV-091)
        return {}
    try:
        import urllib.request

        base = target.split("?")[0].rstrip("/")
        with urllib.request.urlopen(f"{base}/api/stats", timeout=10) as response:
            stats = json.loads(response.read().decode("utf-8", "replace"))
        return stats if isinstance(stats, dict) else {}
    except Exception:
        return {}


# ⛔ MIRRORS `tabApplicable()` IN `senzing_viz_server.py` — the app is the authority, and
# `tests/test_capture_suppressed_tabs.py` → `test_python_rule_matches_the_apps_javascript_rule`
# asserts the two agree (it parses `tabApplicable()` out of the server and compares the gated
# tab set, the stats field each gates on, and the literal thresholds), because a silent
# divergence here is the whole defect this function exists to fix. If you change one, change
# both. (`tests/test_capture_tabs.py` is a different guard: tab *inventory* against the
# contract's table, not these applicability rules.)
#
# The app hides a tab whose data does not exist rather than showing an empty one, so a tab
# that is suppressed was never on screen for the bootcamper. Capturing it anyway produced a
# near-empty PNG under a confident slug ("Cross-Source" over 700px of background) and, worse,
# counted it as covered — the recap's `N of M images` denominator comes from the manifest's
# `captured` list, so an over-count there is a perfect score against a set that was never
# offered. That is the mirror of the under-count the manifest was introduced to prevent.
_APPLICABILITY = {
    "overlap": lambda s: (s.get("data_sources_total") or 0) >= 2,
    "features": lambda s: (s.get("multi_record_entities") or 0) > 0,
    "matchkeys": lambda s: (s.get("multi_record_entities") or 0) > 0,
}


def _tabs_applicable(stats: dict, tabs) -> tuple:
    """Split ``tabs`` into (applicable, suppressed) according to the app's own rule.

    With no stats every tab is applicable, so an unreadable page degrades to today's
    behavior rather than capturing nothing.
    """
    if not stats:
        return list(tabs), []
    applicable, suppressed = [], []
    for tab in tabs:
        rule = _APPLICABILITY.get(tab)
        (applicable if rule is None or rule(stats) else suppressed).append(tab)
    return applicable, suppressed


def _tabs_present(source: str, tabs) -> tuple:
    """Split ``tabs`` into (present, absent) according to the page's own markup.

    ⛔ This pre-flight is what keeps a filename honest. Without it, asking for a tab the
    app does not have still produces a PNG: the injected ``activate()`` finds no
    ``tab-<id>`` element, exhausts its retries, and the **default** tab is captured — so
    e.g. ``viz-feature-scores.png`` would contain the Entity Graph. A file named for a
    tab it does not show is the exact defect tab-naming exists to prevent, so a tab that
    is not in the page is skipped and reported rather than captured wrongly.

    A tab hidden at runtime by ``tabApplicable`` still has its ``tab-<id>`` section in
    the markup and still activates, so this only rejects genuinely absent tabs — a
    suppressed one is caught by ``_tabs_applicable`` instead, and the two are kept apart
    on purpose: **absent** means the tab inventory has drifted (a real problem), while
    **suppressed** means this dataset does not have that tab's data (routine). Reporting
    one as the other would send a reader looking for the wrong fault.

    When the source cannot be read, every tab is treated as present (best-effort — never
    let an unreadable page block capture).
    """
    if not source:
        return list(tabs), []
    present, absent = [], []
    for tab in tabs:
        if re.search(rf'id\s*=\s*["\']tab-{re.escape(tab)}["\']', source) or re.search(
            rf'["\']{re.escape(tab)}["\']\s*,\s*["\']', source
        ):
            present.append(tab)
        else:
            absent.append(tab)
    return present, absent


def _snapshot_copy(html: Path, tab: str) -> Path:
    """Write a temp sibling copy of ``html`` that activates ``tab`` on load.

    A sibling (not /tmp) so any relative asset reference still resolves, and so the
    offline guarantee is unaffected.
    """
    source = html.read_text(encoding="utf-8", errors="surrogateescape")
    script = _ACTIVATE_JS.replace("__TAB__", tab)
    if "</body>" in source:
        patched = source.replace("</body>", script + "</body>", 1)
    else:
        patched = source + script
    handle, path = tempfile.mkstemp(
        prefix=f".{html.stem}-{tab}-", suffix=".html", dir=str(html.parent)
    )
    os.close(handle)
    temp = Path(path)
    temp.write_text(patched, encoding="utf-8", errors="surrogateescape")
    return temp


def _capture_playwright(url: str, out: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": _WINDOW[0], "height": _WINDOW[1]})
            # A self-contained file:// page produces no network events, so
            # "networkidle" can hang or fire inconsistently; wait for "load"
            # and give the D3 force layout a bounded moment to settle.
            page.goto(url, wait_until="load")
            page.wait_for_timeout(2500)
            if _single_page_mode():
                height = None
                try:
                    height = int(page.evaluate(
                        "Math.max(document.documentElement.scrollHeight,"
                        " document.body ? document.body.scrollHeight : 0)"
                    ))
                except Exception:
                    height = None
                if height and height > _MAX_FULL_PAGE_PX:
                    # Clamp by shrinking the viewport and taking a viewport shot: a
                    # full_page shot would ignore the clamp entirely.
                    page.set_viewport_size(
                        {"width": _WINDOW[0], "height": _MAX_FULL_PAGE_PX}
                    )
                    page.wait_for_timeout(400)
                    page.screenshot(path=str(out))
                    _record_full_page(FULL_PAGE_CLAMPED, height, _MAX_FULL_PAGE_PX)
                else:
                    page.screenshot(path=str(out), full_page=True)
                    _record_full_page(FULL_PAGE_FULL, height, height)
            else:
                page.screenshot(path=str(out))
            page.close()
            browser.close()
        return out.is_file() and out.stat().st_size > 0
    except Exception:
        return False


def _capture_selenium(url: str, out: Path) -> bool:
    try:
        from selenium import webdriver  # type: ignore
        from selenium.webdriver.chrome.options import Options  # type: ignore
    except Exception:
        return False
    try:
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=opts)
    except Exception:
        return False
    try:
        driver.set_window_size(*_WINDOW)
        driver.get(url)
        import time

        time.sleep(2.5)
        if _single_page_mode():
            # Selenium has no full-page screenshot, so grow the window to the content and
            # re-shoot.
            #
            # ⛔ `set_window_size` sets the OUTER window, and the viewport is shorter by the
            # window chrome — the same trap as the Chrome CLI's `--window-size`, and it is
            # NOT negligible under `--headless=new`. Measured 2026-08-14: sizing the window
            # to a 2704px page rendered a 2565px viewport, so the capture lost the bottom
            # 139px — the whole footer — while this function still reported a FULL capture
            # and the label still read "Full page". That is an INV-235 breach produced by
            # assuming the two agree, so the offset is now measured from `innerHeight` and
            # added back, exactly as `_measure_chrome_cli` does for the CLI path.
            height = None
            try:
                height = int(driver.execute_script(
                    "return Math.max(document.documentElement.scrollHeight,"
                    " document.body ? document.body.scrollHeight : 0);"
                ))
            except Exception:
                height = None
            if height:
                captured = min(height, _MAX_FULL_PAGE_PX)
                driver.set_window_size(_WINDOW[0], captured)
                time.sleep(0.75)
                # One correction pass: the chrome offset is a constant for the session, so
                # measuring it once and adding it back is enough — no need to iterate.
                try:
                    inner = int(driver.execute_script("return window.innerHeight;"))
                except Exception:
                    inner = 0
                if inner and inner < captured:
                    driver.set_window_size(_WINDOW[0], captured + (captured - inner))
                    time.sleep(0.75)
                _record_full_page(
                    FULL_PAGE_CLAMPED if height > _MAX_FULL_PAGE_PX else FULL_PAGE_FULL,
                    height,
                    captured,
                )
            else:
                # Measurement failed: capture what we can and say it is the viewport.
                _record_full_page(FULL_PAGE_VIEWPORT, None, _WINDOW[1])
        return bool(driver.save_screenshot(str(out)))
    except Exception:
        return False
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# Where Windows installers put Chrome and Edge, relative to an environment variable.
#
# Windows puts neither browser on `PATH`, so `shutil.which()` finds nothing while both
# executables sit on disk — which is how a Windows 11 machine carrying Edge *and* Chrome
# reported "No headless screenshot capability available" and lost every recap screenshot.
# The variables are expanded at call time rather than hard-coded: the drive letter varies,
# and `Program Files` is localized on non-English installs.
_WINDOWS_BROWSER_PATHS = (
    ("PROGRAMFILES", r"Google\Chrome\Application\chrome.exe"),
    ("PROGRAMFILES(X86)", r"Google\Chrome\Application\chrome.exe"),
    ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
    ("PROGRAMFILES", r"Microsoft\Edge\Application\msedge.exe"),
    ("PROGRAMFILES(X86)", r"Microsoft\Edge\Application\msedge.exe"),
    ("LOCALAPPDATA", r"Microsoft\Edge\Application\msedge.exe"),
)

# Registry fallback for a browser installed somewhere non-standard.
_WINDOWS_APP_PATHS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
_WINDOWS_APP_PATHS_EXES = ("chrome.exe", "msedge.exe")


def _windows_browser_candidates() -> list:
    """Absolute Chrome/Edge paths to try on Windows, in preference order.

    Returned whether or not they exist, so the failure message can name what was
    searched — being told a capability is absent when it is present sends the reader to
    install software they already have.
    """
    candidates = []
    for variable, relative in _WINDOWS_BROWSER_PATHS:
        base = os.environ.get(variable)
        if base:
            candidates.append(os.path.join(base, relative))
    return candidates


def _windows_registry_browsers() -> list:
    """Chrome/Edge paths registered under `App Paths`, best-effort.

    Any failure — no `winreg` (non-Windows), key absent, permission denied — yields
    nothing and leaves the path probe as the answer, never an exception.
    """
    try:
        import winreg  # type: ignore
    except Exception:
        return []
    found = []
    for exe in _WINDOWS_APP_PATHS_EXES:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, f"{_WINDOWS_APP_PATHS_KEY}\\{exe}") as key:
                    value = winreg.QueryValue(key, None)
            except Exception:
                continue
            if value:
                found.append(value.strip('"'))
    return found


def _chrome_search_paths() -> list:
    """Every location `_chrome_exe` inspects, in order — the lookup, made reportable."""
    paths = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "msedge",
        "microsoft-edge",
        "microsoft-edge-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    if os.name == "nt":
        paths.extend(_windows_browser_candidates())
        paths.extend(_windows_registry_browsers())
    return paths


def _chrome_exe():
    for cand in _chrome_search_paths():
        if os.sep in cand or "/" in cand:
            if os.path.exists(cand):
                return cand
        elif shutil.which(cand):
            return cand
    return None


def _measure_chrome_cli(exe: str, url: str):
    """``(page_height, window_chrome_px)`` for a ``file://`` url, or ``(None, 0)``.

    Chrome's CLI cannot evaluate an expression for us and has no full-page screenshot
    flag, so the height is read the only way available: stamp it into an attribute from
    injected JS and serialize the DOM. This works for the `file://` pages the bootcamp
    captures; a remote URL cannot be patched, so it returns None and the caller degrades
    to a viewport capture with an honest label rather than guessing a height.

    ⛔ **`--window-size` is not the viewport, and the difference silently crops.** Under
    `--headless=new` Chrome reserves window chrome, so a requested 1440×900 window renders
    an 813px viewport while the screenshot comes out 900px tall — the extra being blank
    padding. Screenshotting at exactly `scrollHeight` therefore loses the last ~87px of a
    tall page: measured live 2026-08-14 on a 2671px page whose footer occupied 2613-2671,
    it produced a 2671px PNG with white where the footer should be. So the offset is
    measured here (requested window height minus the `innerHeight` actually rendered) and
    added back by the caller, rather than hard-coded — it varies with Chrome version and
    platform, and a stale constant would crop exactly this quietly again.
    """
    if not url.startswith("file://"):
        return None, 0
    try:
        # url2pathname, not a manual strip: it decodes %20 and gets the Windows
        # /C:/... form right, both of which a hand-rolled slice gets wrong (INV-001).
        from urllib.request import url2pathname

        source_path = Path(url2pathname(urlparse(url).path))
        if not source_path.is_file():
            return None, 0
        source = source_path.read_text(encoding="utf-8", errors="surrogateescape")
        if "</body>" in source:
            patched = source.replace("</body>", _MEASURE_JS + "</body>", 1)
        else:
            patched = source + _MEASURE_JS
        handle, path = tempfile.mkstemp(
            prefix=f".{source_path.stem}-measure-",
            suffix=".html",
            dir=str(source_path.parent),
        )
        os.close(handle)
        temp = Path(path)
    except Exception:
        return None, 0
    try:
        temp.write_text(patched, encoding="utf-8", errors="surrogateescape")
        done = subprocess.run(
            [
                exe,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={_WINDOW[0]},{_WINDOW[1]}",
                f"--virtual-time-budget={_virtual_time_ms(_CURRENT_TAB)}",
                "--dump-dom",
                _to_url(str(temp)),
            ],
            check=False,
            capture_output=True,
            timeout=90,
        )
        dom = done.stdout.decode("utf-8", "replace")
        found = _MEASURED_HEIGHT_RE.search(dom)
        if not found:
            return None, 0
        inner = _MEASURED_INNER_RE.search(dom)
        # Positive offset only: if innerHeight somehow exceeds the request, adding a
        # negative would crop rather than pad.
        chrome_px = max(0, _WINDOW[1] - int(inner.group(1))) if inner else 0
        return int(found.group(1)), chrome_px
    except Exception:
        return None, 0
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def _capture_chrome_cli(url: str, out: Path) -> bool:
    exe = _chrome_exe()
    if exe is None:
        return False
    height = _WINDOW[1]
    if _single_page_mode():
        measured, chrome_px = _measure_chrome_cli(exe, url)
        if measured:
            covered = min(measured, _MAX_FULL_PAGE_PX)
            # Request viewport-worth PLUS the window chrome, so `covered` px of PAGE is
            # what actually renders. Without this the last `chrome_px` of the page is cut.
            height = covered + chrome_px
            _record_full_page(
                FULL_PAGE_CLAMPED if measured > _MAX_FULL_PAGE_PX else FULL_PAGE_FULL,
                measured,
                covered,
            )
        else:
            _record_full_page(FULL_PAGE_VIEWPORT, None, _WINDOW[1])
    try:
        subprocess.run(
            [
                exe,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={_WINDOW[0]},{height}",
                f"--virtual-time-budget={_virtual_time_ms(_CURRENT_TAB)}",
                f"--screenshot={out}",
                url,
            ],
            check=False,
            capture_output=True,
            timeout=90,
        )
    except Exception:
        return False
    return out.is_file() and out.stat().st_size > 0


def _capture_wkhtmltoimage(url: str, out: Path) -> bool:
    if not shutil.which("wkhtmltoimage"):
        return False
    try:
        subprocess.run(
            [
                "wkhtmltoimage",
                "--width",
                str(_WINDOW[0]),
                "--javascript-delay",
                "3000",
                url,
                str(out),
            ],
            check=False,
            capture_output=True,
            timeout=90,
        )
    except Exception:
        return False
    ok = out.is_file() and out.stat().st_size > 0
    if ok and _single_page_mode():
        # `--width` with no `--height` renders the full content height by design, so this
        # backend is already whole-document and needs no measurement pass. The clamp
        # therefore does not apply here; it is the last-resort backend, and stating the
        # exemption is better than implying a clamp that is not enforced.
        _record_full_page(FULL_PAGE_FULL, None, None)
    return ok


_BACKENDS = (
    _capture_playwright,
    _capture_selenium,
    _capture_chrome_cli,
    _capture_wkhtmltoimage,
)


# The tab currently being captured, so a backend can size its settle time without every
# backend signature growing a parameter — `_BACKENDS` is called uniformly, and tests
# substitute two-argument callables for it.
#
# This is correct ONLY because captures run strictly one at a time: `capture()` walks the
# tabs in a loop, and `_capture_one` owns the global for the duration of exactly one
# capture. Parallelizing that loop — the obvious optimization on a step that shells out to
# a browser per tab — would apply one tab's virtual-time budget to another tab's capture,
# and the symptom is a subtly under-settled PNG rather than an error: the quiet way to
# break INV-122's guarantee that each file shows the tab it is named after. If capture is
# ever parallelized, thread the tab through the backend signature instead of this global.
# `_capture_one` says so on stderr if a second capture begins while one is in flight, so
# the change announces itself instead of silently mis-sizing a settle budget.
_CURRENT_TAB = ""
_CAPTURE_IN_FLIGHT = False

# What the single-page capture actually achieved, and the two heights that decided it.
# Reset per capture by `_capture_one`, set by whichever backend won, read by `_tab_label`.
# Defaults to VIEWPORT so a backend that never records an outcome cannot inherit the
# "Full page" claim by silence — the failure mode this whole change is about.
_FULL_PAGE_OUTCOME = FULL_PAGE_VIEWPORT
_FULL_PAGE_HEIGHT = None
_FULL_PAGE_CAPTURED = None


def _single_page_mode() -> bool:
    """True when the capture in flight is the whole-document mode, not a tab."""
    return _CURRENT_TAB == SINGLE_PAGE_ID


def _record_full_page(outcome: str, page_height=None, captured_height=None) -> None:
    """Record what a single-page capture achieved, and warn when it fell short."""
    global _FULL_PAGE_OUTCOME, _FULL_PAGE_HEIGHT, _FULL_PAGE_CAPTURED
    _FULL_PAGE_OUTCOME = outcome
    _FULL_PAGE_HEIGHT = page_height
    _FULL_PAGE_CAPTURED = captured_height
    if outcome == FULL_PAGE_FULL:
        return
    if outcome == FULL_PAGE_CLAMPED:
        sys.stderr.write(
            "capture_screenshots: page is %spx tall, above the %dpx clamp — captured the "
            "top %dpx and labelled it as clamped, not as the full page.\n"
            % (page_height, _MAX_FULL_PAGE_PX, _MAX_FULL_PAGE_PX)
        )
        return
    sys.stderr.write(
        "capture_screenshots: could not capture the full page; captured the viewport only "
        "(%spx of a %spx page). The label says so — do NOT caption this as the full page "
        "(INV-123).\n"
        % (
            captured_height if captured_height is not None else _WINDOW[1],
            page_height if page_height is not None else "unknown",
        )
    )


# Injected into a temp copy for the Chrome-CLI measurement pass. Chrome's `--dump-dom`
# serializes the DOM *after* scripts run, so an attribute this sets is visible in that
# output — which is the only way to read a computed layout height from a CLI that cannot
# evaluate an expression for us. Stamped on a delay for the same reason captures settle:
# the page's own layout has to finish first.
_MEASURE_JS = """
<script>
(function(){
  function stamp(){
    try {
      var d = document.documentElement, b = document.body;
      var h = Math.max(d.scrollHeight, d.offsetHeight,
                       b ? b.scrollHeight : 0, b ? b.offsetHeight : 0);
      d.setAttribute("data-sz-scroll-height", String(h));
      d.setAttribute("data-sz-inner-height", String(window.innerHeight));
    } catch (e) {}
  }
  if (document.readyState === "complete") { setTimeout(stamp, 1500); }
  else { window.addEventListener("load", function(){ setTimeout(stamp, 1500); }); }
})();
</script>
"""
_MEASURED_HEIGHT_RE = re.compile(r'data-sz-scroll-height="(\d+)"')
_MEASURED_INNER_RE = re.compile(r'data-sz-inner-height="(\d+)"')


def _capture_one(url: str, out: Path, backend=None, tab: str = ""):
    """Capture ``url`` to ``out``; return the backend that worked, else None.

    Returning the winner lets the caller reuse it for the remaining tabs instead of
    re-walking the list — which would multiply the cost of every missing backend by
    the number of tabs.
    """
    global _CURRENT_TAB, _CAPTURE_IN_FLIGHT
    global _FULL_PAGE_OUTCOME, _FULL_PAGE_HEIGHT, _FULL_PAGE_CAPTURED
    # Reset before every capture, so one page's outcome can never label the next one.
    _FULL_PAGE_OUTCOME, _FULL_PAGE_HEIGHT, _FULL_PAGE_CAPTURED = (
        FULL_PAGE_VIEWPORT, None, None,
    )
    if _CAPTURE_IN_FLIGHT:
        # Warn, never raise: a capture step must not block the module (INV-052/INV-048).
        sys.stderr.write(
            "capture_screenshots: a capture started while another was still in flight. "
            "`_CURRENT_TAB` is a single module global, so the virtual-time budget may be "
            "sized for the wrong tab and a PNG may be captured under-settled (INV-122). "
            "Thread the tab through the backend signature rather than capturing in "
            "parallel.\n"
        )
    _CAPTURE_IN_FLIGHT = True
    _CURRENT_TAB = tab
    try:
        for candidate in (backend,) if backend else _BACKENDS:
            if candidate(url, out):
                return candidate
        return None
    finally:
        _CAPTURE_IN_FLIGHT = False


def resolve_tabs(spec: str) -> list:
    """Parse a --tabs value into known tab ids, preserving the given order."""
    if not spec or spec.strip().lower() == "all":
        # `all` is an explicit spelling of the default, so a caller can state intent
        # rather than relying on an omission that reads like "none".
        return list(DEFAULT_TABS)
    wanted, unknown = [], []
    for raw in re.split(r"[,\s]+", spec.strip()):
        if not raw:
            continue
        tab = raw.strip().lower()
        if tab in TABS:
            if tab not in wanted:
                wanted.append(tab)
        else:
            unknown.append(raw)
    if unknown:
        raise ValueError(
            f"unknown tab id(s): {', '.join(unknown)}. Tab ids: {', '.join(DEFAULT_TABS)}"
        )
    retired = [t for t in wanted if t in RESERVED_TABS]
    if retired:
        # Accepted, so an old eight-tab snapshot still captures under its own slugs —
        # but say so, or a caller who read a stale list never learns the tab is gone.
        sys.stderr.write(
            "note: %s names a tab the current app no longer serves; it is kept only for "
            "snapshots saved before the tab set was fixed at six. A current app will "
            "report it as not present.\n" % ", ".join(retired)
        )
    return wanted


def manifest_path(out_dir: Path, name: str) -> Path:
    """Where the sidecar manifest for ``name`` lives — beside its PNGs."""
    return Path(out_dir) / f"{name}-tabs.json"


def write_manifest(
    out_dir: Path, name: str, requested, absent, written, missed, suppressed=()
) -> bool:
    """Record what capture did, beside the PNGs. Returns True if written.

    Best-effort like capture itself (INV-122): a manifest that cannot be written is
    reported on stderr and never fails the run — the PNGs are the deliverable. But it
    is reported, because a silently absent manifest downgrades the coverage check to
    "skipped" much later, in graduation, where the cause is no longer visible.
    """
    suppressed = list(suppressed)
    slug_of = {
        tab: (SINGLE_PAGE_ID if tab == SINGLE_PAGE_ID else TABS.get(tab, (tab, tab))[0])
        for tab in requested
    }
    captured_tabs = [
        tab
        for tab in requested
        if _out_path(Path(out_dir), name, tab) in {p for p, _ in written}
    ]
    payload = {
        "schema": MANIFEST_SCHEMA,
        "name": name,
        # Every tab asked for, before the page was consulted.
        "requested": list(requested) + list(absent) + suppressed,
        "captured": [
            {
                "tab": tab,
                "slug": slug_of.get(tab, tab),
                "file": _out_path(Path(out_dir), name, tab).name,
                "label": _tab_label(tab),
            }
            for tab in captured_tabs
        ],
        # Three different reasons a tab produced nothing. Keeping them apart matters:
        # "not in this app" means the tab inventory drifted, "not applicable" is routine
        # and correct, and "capture failed" is a real loss. A reader chasing a missing
        # recap image needs to know which of the three they are looking at.
        "not_present": [{"tab": tab, "reason": "not present in this visualization"}
                        for tab in absent],
        "not_applicable": [
            {"tab": tab,
             "reason": "the app suppresses this tab because its data does not exist"}
            for tab in suppressed
        ],
        "failed": [{"tab": tab, "reason": "no image written by any backend"}
                   for tab in missed],
    }
    payload["captured_count"] = len(payload["captured"])
    payload["requested_count"] = len(payload["requested"])
    target = manifest_path(Path(out_dir), name)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as exc:
        print(
            f"could not write the tab manifest {target} ({exc}); the recap's "
            "tab-coverage check will report itself skipped rather than passed.",
            file=sys.stderr,
        )
        return False
    return True


def capture(
    target: str,
    out_dir: Path,
    name: str,
    tabs,
    query: str = "",
    is_url: bool = False,
) -> list:
    """Capture one PNG per tab; return ``(path, label)`` for each one written."""
    if not _is_local_target(target):
        raise ValueError(_NON_LOCAL_TARGET.format(target=target))
    out_dir.mkdir(parents=True, exist_ok=True)
    html = None if is_url else Path(target)
    if html is not None and not html.is_file():
        raise ValueError(f"no such HTML file: {target}")

    written = []
    working_backend = None
    for tab in tabs:
        out = _out_path(out_dir, name, tab)
        temp = None
        try:
            if tab == SINGLE_PAGE_ID:
                # The page as it loads: no ?tab= deep link, and no activation copy —
                # there is nothing to activate, and injecting one would only add a
                # script that finds no tab and exhausts its retries.
                url = target if is_url else _to_url(str(html))
            elif is_url:
                url = _tab_url(target, tab, query)
            else:
                temp = _snapshot_copy(html, tab)
                url = _to_url(str(temp))
            winner = _capture_one(url, out, working_backend, tab=tab)
            if winner is not None:
                working_backend = winner
                written.append((out, _tab_label(tab)))
            elif working_backend is None:
                # Nothing worked for the first tab: no headless capability at all,
                # so stop rather than failing identically for every remaining tab.
                break
        finally:
            if temp is not None:
                try:
                    temp.unlink()
                except OSError:
                    pass
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Capture one PNG per tab of a local bootcamp visualization."
    )
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--html", help="Path to a local HTML snapshot to screenshot.")
    source.add_argument(
        "--url", help="localhost URL of the running visualization app (enables ?tab=/&q=)."
    )
    ap.add_argument(
        "--out-dir",
        default="docs/visualizations",
        help="Directory to write PNGs into (default: docs/visualizations).",
    )
    ap.add_argument(
        "--name",
        default="visualization",
        help="Base name for the PNG files (default: visualization).",
    )
    ap.add_argument(
        "--tabs",
        default="",
        help=f"Comma-separated tab ids, or 'all' (default, and the app's full tab set: "
        f"{','.join(DEFAULT_TABS)}). An omitted --tabs means ALL tabs, not none — for a "
        f"page with no tabs use --single.",
    )
    ap.add_argument(
        "--single",
        action="store_true",
        help="Capture the whole page as ONE image, for a single-page deliverable with no "
        "tabs (writes {name}.png). Cannot be combined with --tabs.",
    )
    ap.add_argument(
        "--query",
        default="",
        help="Search text for the Search / Probe tab; requires --url (the static "
        "snapshot has no engine to search).",
    )
    args = ap.parse_args(argv)

    if args.single and args.tabs:
        print(
            "--single captures the page as one image and --tabs names tabs to capture; "
            "pass one or the other.",
            file=sys.stderr,
        )
        return 1
    if args.single:
        tabs = [SINGLE_PAGE_ID]
    else:
        try:
            tabs = resolve_tabs(args.tabs)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if not tabs:
        print("no tabs to capture", file=sys.stderr)
        return 1
    if args.query and not args.url:
        print(
            "--query needs --url: the static snapshot has no running engine, so its "
            "Search / Probe tab cannot show results (see snapshot-static-search-results).",
            file=sys.stderr,
        )
        return 1

    target = args.url or args.html
    is_url = bool(args.url)
    # Refuse a non-local target *before* the pre-flight below reads the page. The same
    # check in capture() runs later, which is too late to keep the promise: the
    # pre-flight would already have fetched the remote host (offline guarantee, INV-091).
    if not _is_local_target(target):
        print(_NON_LOCAL_TARGET.format(target=target), file=sys.stderr)
        return 1
    if not is_url and not Path(target).is_file():
        print(f"no such HTML file: {target}", file=sys.stderr)
        return 1

    # Pre-flight: never capture a tab the page does not have (see _tabs_present), nor one
    # the app suppressed because its data does not exist (see _tabs_applicable).
    source = _page_source(target, is_url)
    absent = []
    suppressed = []
    if tabs != [SINGLE_PAGE_ID]:
        tabs, absent = _tabs_present(source, tabs)
        for tab in absent:
            print(
                f"tab {tab!r} is not present in this visualization; skipping it rather than "
                "capturing the default tab under its name.",
                file=sys.stderr,
            )
        tabs, suppressed = _tabs_applicable(_page_stats(source, target, is_url), tabs)
        for tab in suppressed:
            print(
                f"tab {tab!r} is not applicable to this data, so the app does not show it; "
                "skipping it rather than capturing an empty pane the bootcamper never saw.",
                file=sys.stderr,
            )
    if not tabs and not _has_tab_controls(source):
        # Safety net: the page has no tab bar at all, so this is a single-page document
        # rather than a tabbed app whose tabs were misnamed. Capture it whole instead of
        # exiting empty — exiting was the behavior that silently cost every single-page
        # deliverable its recap image.
        print(
            "This page has no tab controls, so none of the requested tabs could exist; "
            "capturing it as a single page instead. Pass --single to say so explicitly. "
            f"Requested: {', '.join(absent + suppressed)}.",
            file=sys.stderr,
        )
        tabs, absent, suppressed = [SINGLE_PAGE_ID], [], []
    elif not tabs:
        # A tabbed app that offered none of the requested tabs. Report and skip (INV-122) —
        # capturing the whole page here would put the default tab in a file named for a
        # tab it does not show, which is the defect tab-naming exists to prevent.
        # Distinct from "no headless backend" — saying the wrong reason here would be
        # the same class of defect this script exists to stop.
        #
        # ⛔ The two reasons are reported separately even when both are empty-handed,
        # because they send a reader to different places: a misnamed tab means the
        # inventory drifted, while a suppressed one means this dataset simply has no such
        # data and the run was fine. Collapsing them into "none of these tabs exist" would
        # report a routine single-source bootcamp as a broken tab inventory.
        if absent:
            print(
                "None of the requested tabs exist in this visualization; nothing to "
                f"capture. Requested: {', '.join(absent)}.",
                file=sys.stderr,
            )
        if suppressed:
            print(
                "Every requested tab is inapplicable to this data, so the app shows none "
                f"of them; nothing to capture. Requested: {', '.join(suppressed)}.",
                file=sys.stderr,
            )
        # Still record it: "this app offered none of these tabs" is a real answer to
        # "how many tabs should the recap show", and the only one available here.
        write_manifest(Path(args.out_dir), args.name, [], absent, [], [], suppressed)
        return 2

    try:
        written = capture(
            target, Path(args.out_dir), args.name, tabs, query=args.query, is_url=is_url
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Written before the no-capture branches below, because a run that captured
    # nothing is exactly the case the recap's coverage check must be able to see.
    _missed = [
        t
        for t in tabs
        if _out_path(Path(args.out_dir), args.name, t) not in {p for p, _ in written}
    ]
    write_manifest(
        Path(args.out_dir), args.name, tabs, absent, written, _missed, suppressed
    )

    if not written:
        # Two different failures used to share one message, and the shared wording named
        # the wrong cause: a Windows machine with Edge and Chrome installed was told no
        # capability was available, which sends the reader to install software they
        # already have. Distinguish "nothing to run" from "it ran and produced nothing"
        # (INV-122 requires the reported reason to be the actual one).
        browser = _chrome_exe()
        if browser is None:
            searched = "; ".join(_chrome_search_paths())
            print(
                "No headless screenshot capability available. Tried Playwright, "
                "Selenium, headless Chrome/Chromium, wkhtmltoimage. No Chrome, "
                "Chromium or Edge executable was found — searched: "
                f"{searched}. If a browser is installed elsewhere, put it on PATH. "
                "Skipping screenshots; keep the HTML link instead.",
                file=sys.stderr,
            )
        else:
            print(
                f"A browser was found ({browser}) but every capture attempt failed, so "
                "no image was written. This is not a missing install — do not install "
                "anything. Re-run and check the browser's own error output; if the "
                "target is a live server, confirm it is still serving. Skipping "
                "screenshots; keep the HTML link instead.",
                file=sys.stderr,
            )
        return 2

    missed = _missed
    if missed:
        # Never a silent partial result: say which tabs produced nothing.
        print(
            f"Captured {len(written)}/{len(tabs)} tabs; no image for: {', '.join(missed)}.",
            file=sys.stderr,
        )

    for path, label in written:
        print(f"{os.path.relpath(path)}\t{label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
