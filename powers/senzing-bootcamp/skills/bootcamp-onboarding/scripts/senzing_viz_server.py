#!/usr/bin/env python3
"""Bundled Senzing entity-resolution visualization web app — the shipped reference.

Per INV-090 the Truth Set visualization server is built in the bootcamper's chosen
programming language, modeled on this reference and the ``visualization-api-reference.md``
contract; this Python script is run directly only when the chosen language is Python. It
delivers the standalone **Truth Set visualization module** (Module 3b) "wow moment" and is
reused for Module 7 result views. System Verification (Module 3) uses synthetic data and
does not visualize (INV-082/INV-087).

It builds an entity model from the records the bootcamper loaded (by looking each
one up through the Senzing SDK, so all data comes from real entity resolution),
then serves:

- ``GET /``            single-page D3 v7 visualization (all tabs + summary banner)
- ``GET /api/stats``   aggregate resolution statistics (incl. per-bucket entity lists
  under ``bucket_entities`` for the clickable histogram, and ``data_sources_total``)
- ``GET /api/graph``   entity nodes + relationship edges (the Entity Graph tab, in both
  its full-population and relationship-subgraph modes)
- ``GET /api/merges``  multi-record entities with constituent records
- ``GET /api/search``  search-by-attributes with resolution reasoning
- ``GET /api/why``     explain WHY the records in an entity resolved together
  (``why_records`` / ``why_record_in_entity``); ``?entity_id=<id>``
- ``GET /api/how``     explain HOW an entity was constructed from its records
  (``how_entity_by_entity_id``); ``?entity_id=<id>``
- ``GET /api/records?entity_id=``  the constituent records of one entity
- ``GET /api/overlap``    cross-source overlap matrix (which sources share entities)
- ``GET /api/matchkeys``  match-key frequency (which feature combos drive resolutions)
- ``GET /api/features``   feature-score distribution across a capped sample of
  multi-record entities (from ``why_records``; degrades gracefully)

These endpoints back a single consolidated, tabbed visualization app — the one artifact
Module 7 offers for results visualization (it no longer produces separate static pages).
Its tab set is exactly **six** (INV-155), in this order: Entity Graph, Merge Statistics,
Match Keys, Feature Scores, Cross-Source, Search / Probe. The row order of the tab table
in ``module-03b-truthset-visualization/visualization-api-reference.md`` is the ordering
authority (INV-147); a tab is shown only when its data exists.

Two former tabs were **removed** and their unique capabilities live on inside that six:
the standalone *Relationship Network* tab is now the Entity Graph's "Show only entities
with relationships" **mode** (same ``/api/graph`` payload), and *Record Merges* is now the
"Show all merged entities" button on Search / Probe (``/api/merges``). There is no Results
Dashboard tab either — the entity-size distribution is the Merge Statistics histogram
(``/api/stats``), not a separate view. Their ids stay reserved rather than reused; see the
``TABS`` note in ``capture_screenshots.py``.

Data source: ``get_entity_by_record_id`` with ``SZ_ENTITY_DEFAULT_FLAGS`` (which
includes ``SZ_ENTITY_INCLUDE_ALL_RELATIONS``), so nodes and edges come from one
call per loaded record. No direct SQL is ever run against the database.

Usage:
    # Serve the live web app (Python reference; run directly only when the chosen language is Python — INV-090):
    python3 senzing_viz_server.py --records src/system_verification/truthset_data.jsonl

    # Also write a persistent standalone snapshot (no server needed to view):
    python3 senzing_viz_server.py --records data/senzing-ready/*.jsonl \\
        --snapshot docs/visualizations/results.html

    # Just build the snapshot and exit (no server), used by the completion gate:
    python3 senzing_viz_server.py --records src/system_verification/truthset_data.jsonl \\
        --snapshot docs/visualizations/truthset_verification.html --no-serve

Settings resolution, in this order — the precedence is **content-aware**, not
existence-based:

1. ``--settings`` (default ``config/engine_config.json``) when the file exists AND its
   ``PIPELINE`` carries ``CONFIGPATH``, ``RESOURCEPATH`` and ``SUPPORTPATH``.
2. ``SENZING_ENGINE_CONFIGURATION_JSON`` when the file is absent, unreadable, or
   incomplete and the env var is complete. Which source won is stated on stderr whenever
   both are present.
3. Otherwise the run fails, naming the source it used and the ``PIPELINE`` keys that are
   missing — it does NOT proceed into the engine.

⛔ Step 3 exists because proceeding produced a **misleading** failure. A file containing
``{"PIPELINE": {}}`` is valid JSON and truthy, so an emptiness check passes, and the engine
then aborts with ``SENZ7426`` (transliteration). That error means ``SUPPORTPATH`` is wrong —
``explain_error_code('7426')`` says "Check SUPPORTPATH FIRST … This is a configuration
error, NOT a broken install" — so the reader is sent to fix a ``SUPPORTPATH`` that is
correct in the place they are looking, while the value actually in force came from a file
they were not told was preferred. Validating first turns a three-step misdiagnosis into one
line naming the real cause.

The Senzing native library must be importable (source the project
``src/scripts/senzing-env.sh`` first).

Exit code 0 means the entity model was built successfully (and, if requested, the
snapshot was written); non-zero means it could not be built.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# Brand tokens ship in this same directory. Import them so the visualization shares
# the Senzing style guide's palette with the recap PDF; fall back to an inlined copy
# of the same values if the module is ever unavailable, so this script keeps working
# in isolation (mirrors the vendored-D3 offline fallback).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Fallback palette, used only if brand_tokens is unavailable. Named at module scope
# so tests/test_brand_sync.py can assert it stays equal to brand_tokens.py — the two
# copies would otherwise drift silently (the runtime prefers the imported values
# whenever brand_tokens loads, so a stale fallback is never exercised in practice).
_FALLBACK_SOURCE_COLORS = {"CUSTOMERS": "#F57826", "REFERENCE": "#3B6EA5", "WATCHLIST": "#C8922A"}
_FALLBACK_COLORS = ["#8b5cf6", "#ec4899", "#0ea5e9", "#a3a34a", "#ef4444", "#14b8a6"]
_FALLBACK_STROKES = ["#FFFFFF", "#18160F", "#FAF8F3"]
_FALLBACK_STROKE_WIDTHS = [1.5, 3.0]
_FALLBACK_FILL_SHADES = [0.0, 0.30, -0.30, 0.55, -0.55]
_FALLBACK_BRAND = {
    "bg": "#FAF8F3", "surface": "#FFFFFF", "dark": "#18160F",
    "ink": "#18160F", "muted": "#4A4640", "accent": "#F57826",
    "accent_hot": "#FF4E1F", "accent_soft": "#FDEEE3",
    "line": "#E5DFD3", "green": "#1D9E75",
    "font": "Roboto, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif",
    "code_font": "'Fira Code', 'Courier New', Courier, monospace",
}
try:
    import brand_tokens as _bt

    SOURCE_COLORS = dict(_bt.SOURCE_COLORS)
    FALLBACK_COLORS = list(_bt.FALLBACK_COLORS)
    SOURCE_STROKES = list(_bt.SOURCE_STROKES)
    SOURCE_STROKE_WIDTHS = list(_bt.SOURCE_STROKE_WIDTHS)
    SOURCE_FILL_SHADES = list(_bt.SOURCE_FILL_SHADES)
    color_for_sources = _bt.color_for_sources
    _BRAND = {
        "bg": _bt.WARM_OFF_WHITE, "surface": _bt.WHITE, "dark": _bt.DEEP,
        "ink": _bt.DARK_INK, "muted": _bt.BODY_INK, "accent": _bt.EMBER_CORE,
        "accent_hot": _bt.EMBER_HOT, "accent_soft": _bt.EMBER_SOFT,
        "line": _bt.WARM_LINE, "green": _bt.SIGNAL_GREEN,
        "font": _bt.FONT_STACK, "code_font": _bt.CODE_FONT_STACK,
    }
except Exception:  # defensive fallback — kept in sync via tests/test_brand_sync.py
    SOURCE_COLORS = dict(_FALLBACK_SOURCE_COLORS)
    FALLBACK_COLORS = list(_FALLBACK_COLORS)
    SOURCE_STROKES = list(_FALLBACK_STROKES)
    SOURCE_STROKE_WIDTHS = list(_FALLBACK_STROKE_WIDTHS)
    SOURCE_FILL_SHADES = list(_FALLBACK_FILL_SHADES)

    def color_for_sources(sources):
        """Inlined mirror of ``brand_tokens.color_for_sources`` (same contract).

        Kept behaviorally identical, not merely similar: tests/test_brand_sync.py asserts
        this returns the same dict as the helper, so the channel widening has to be here
        too or the import-failure path silently reverts to a 24-source ceiling.
        """
        states = 1 + len(SOURCE_STROKES) * len(SOURCE_STROKE_WIDTHS)
        codes = sorted({str(s) for s in (sources or []) if str(s).strip()})
        preferred = {c: SOURCE_COLORS[c] for c in codes if c in SOURCE_COLORS}
        claimed = set(preferred.values())
        available = [c for c in FALLBACK_COLORS if c not in claimed] or list(FALLBACK_COLORS)

        def shade(fill, factor):
            if not factor:
                return fill
            target = "#FFFFFF" if factor > 0 else "#18160F"
            weight = abs(factor)
            rgb = lambda v: (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))  # noqa: E731
            return "#%02X%02X%02X" % tuple(
                round(a + (b - a) * weight) for a, b in zip(rgb(fill), rgb(target))
            )

        assigned, nth = {}, 0
        for code in codes:
            if code in preferred:
                fill, cycle = preferred[code], 0
            else:
                fill = available[nth % len(available)]
                cycle = nth // len(available)
                fill = shade(fill, SOURCE_FILL_SHADES[
                    (cycle // states) % len(SOURCE_FILL_SHADES)])
                nth += 1
            slot = cycle % states
            if slot == 0:
                stroke, width = SOURCE_STROKES[0], None
            else:
                k = slot - 1
                stroke = SOURCE_STROKES[(k + 1) % len(SOURCE_STROKES)]
                width = SOURCE_STROKE_WIDTHS[k // len(SOURCE_STROKES)]
            assigned[code] = {
                "fill": fill,
                "stroke": stroke,
                "stroke_width": width,
                "cycle": cycle,
            }
        return assigned

    _BRAND = dict(_FALLBACK_BRAND)


# --------------------------------------------------------------------------- #
# Entity model (built from the SDK)
# --------------------------------------------------------------------------- #
def _iter_record_keys(patterns):
    """Yield (data_source, record_id) from the loaded JSONL files."""
    seen = set()
    files = []
    for pat in patterns:
        files.extend(sorted(glob.glob(pat)))
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ds = d.get("DATA_SOURCE")
                    rid = d.get("RECORD_ID")
                    if ds is None or rid is None:
                        continue
                    key = (str(ds), str(rid))
                    if key not in seen:
                        seen.add(key)
                        yield key
        except OSError:
            continue


class Model:
    def __init__(self):
        self.records_total = 0
        self.entities = {}   # entity_id -> {...}
        self.edges = {}      # (min,max) -> {match_key, relationship_type}
        # Feature-score distribution, computed once (capped) after build via
        # compute_feature_dist(); an empty default keeps /api/features safe if it
        # was never computed or every why_records call failed (INV-077).
        self.feature_dist = {
            "features": [], "sampled": 0, "multi_record_total": 0, "capped": False
        }

    def build(self, engine, flags, record_keys):
        get = engine.get_entity_by_record_id
        for ds, rid in record_keys:
            self.records_total += 1
            try:
                resp = json.loads(get(ds, rid, flags))
            except Exception:
                continue
            re_ = resp.get("RESOLVED_ENTITY", {})
            eid = re_.get("ENTITY_ID")
            if eid is None:
                continue
            if eid not in self.entities:
                records = re_.get("RECORDS", [])
                sources = sorted({r.get("DATA_SOURCE", "?") for r in records})
                self.entities[eid] = {
                    "entity_id": eid,
                    "entity_name": re_.get("ENTITY_NAME") or f"Entity {eid}",
                    "record_count": len(records),
                    "data_sources": sources,
                    "records": [
                        {
                            "data_source": r.get("DATA_SOURCE", "?"),
                            "record_id": str(r.get("RECORD_ID", "?")),
                            # Per-record match key (how this record joined the
                            # entity); the seed record is typically empty. Drives
                            # the Match Keys tab. Present with the default entity
                            # flags' record-matching-info; falls back to "".
                            "match_key": r.get("MATCH_KEY", "") or "",
                        }
                        for r in records
                    ],
                }
            for rel in resp.get("RELATED_ENTITIES", []):
                tid = rel.get("ENTITY_ID")
                if tid is None:
                    continue
                key = (min(eid, tid), max(eid, tid))
                if key not in self.edges:
                    self.edges[key] = {
                        "match_key": rel.get("MATCH_KEY", ""),
                        "relationship_type": rel.get("MATCH_LEVEL_CODE")
                        or rel.get("ERRULE_CODE")
                        or "RELATED",
                    }
        return self

    def data_sources(self):
        """Every data-source code present in the model, sorted.

        Drives the node/legend colors: they are assigned from the sources actually
        loaded, never from a fixed name-keyed palette (a Truth-Set-keyed map renders
        every real bootcamper's sources in one identical fallback color).
        """
        codes = set()
        for entity in self.entities.values():
            codes.update(entity.get("data_sources", []))
        return sorted(str(c) for c in codes if str(c).strip())

    # ---- API payloads ---------------------------------------------------- #
    def stats(self):
        ents = list(self.entities.values())
        hist = {"1": 0, "2": 0, "3": 0, "4+": 0}
        # Per-bucket entity lists so the histogram bars can be clicked to drill
        # down. Capped per bucket to bound the payload (and the embedded snapshot);
        # the `histogram` counts remain authoritative.
        buckets = {"1": [], "2": [], "3": [], "4+": []}
        all_sources = set()
        for e in ents:
            all_sources.update(e["data_sources"])
            c = e["record_count"]
            b = "4+" if c >= 4 else str(c)
            hist[b] = hist.get(b, 0) + 1
            if len(buckets[b]) < 200:
                buckets[b].append(
                    {
                        "entity_id": e["entity_id"],
                        "entity_name": e["entity_name"],
                        "record_count": c,
                    }
                )
        return {
            "records_total": self.records_total,
            "entities_total": len(self.entities),
            "multi_record_entities": sum(1 for e in ents if e["record_count"] > 1),
            "cross_source_entities": sum(1 for e in ents if len(e["data_sources"]) >= 2),
            "relationships_total": len(self.edges),
            # Distinct data-source count, so the client can decide whether the
            # Cross-Source tab is applicable (needs 2+ sources) without a second call.
            "data_sources_total": len(all_sources),
            "histogram": hist,
            "bucket_entities": buckets,
            # The largest resolved entities. Formerly the only content unique to
            # /api/dashboard; that endpoint and its tab were removed because their
            # counts and histogram duplicated this payload (contract:
            # "De-duplication (required)"). Rendered beneath the histogram.
            "sample_entities": self._sample_entities(),
        }

    def _sample_entities(self, cap=10):
        """Multi-record entities, largest first — the 'biggest merges' list."""
        out = []
        for e in sorted(self.entities.values(), key=lambda x: -x["record_count"]):
            if e["record_count"] < 2:
                break
            out.append(
                {
                    "entity_id": e["entity_id"],
                    "entity_name": e["entity_name"],
                    "record_count": e["record_count"],
                    "data_sources": sorted(set(e["data_sources"])),
                }
            )
            if len(out) >= cap:
                break
        return out

    def records(self, entity_id):
        """The constituent records of one entity — backs the Records action.

        Unlike merges(), this covers single-record entities too, and needs no
        engine call, so it is embedded in the standalone snapshot and works
        offline (contract: GET /api/records).
        """
        try:
            eid = int(entity_id)
        except (TypeError, ValueError):
            return {"entity_id": entity_id, "error": "bad request: entity_id must be an integer"}
        e = self.entities.get(eid)
        if e is None:
            return {"entity_id": eid, "error": "not found: no such entity"}
        return {
            "entity_id": eid,
            "entity_name": e["entity_name"],
            "records": e["records"],
        }

    def overlap(self):
        """Cross-source overlap matrix: for each ordered pair of data sources, the
        number of resolved entities that contain records from both (diagonal = the
        entities present in that source)."""
        src_set = set()
        for e in self.entities.values():
            src_set.update(e["data_sources"])
        sources = sorted(src_set)
        idx = {s: i for i, s in enumerate(sources)}
        n = len(sources)
        matrix = [[0] * n for _ in range(n)]
        for e in self.entities.values():
            ds = sorted(set(e["data_sources"]))
            for s in ds:
                matrix[idx[s]][idx[s]] += 1
            for i in range(len(ds)):
                for j in range(i + 1, len(ds)):
                    a, b = idx[ds[i]], idx[ds[j]]
                    matrix[a][b] += 1
                    matrix[b][a] += 1
        # Per-cell entity lists so heatmap cells drill down, mirroring
        # bucket_entities on /api/stats. Keyed "i,j" with i <= j (the matrix is
        # symmetric, so each pair is stored once).
        cells, capped = {}, False
        for e in self.entities.values():
            ds = sorted(set(e["data_sources"]))
            ent = {
                "entity_id": e["entity_id"],
                "entity_name": e["entity_name"],
                "record_count": e["record_count"],
            }
            keys = [(idx[s], idx[s]) for s in ds]
            keys += [
                (min(idx[ds[i]], idx[ds[j]]), max(idx[ds[i]], idx[ds[j]]))
                for i in range(len(ds))
                for j in range(i + 1, len(ds))
            ]
            for i, j in keys:
                lst = cells.setdefault("%d,%d" % (i, j), [])
                if len(lst) < 200:
                    lst.append(ent)
                else:
                    capped = True
        return {
            "sources": sources,
            "matrix": matrix,
            "cell_entities": cells,
            "cell_capped": capped,
        }

    def match_keys(self):
        """Match-key frequency: how often each per-record match key (e.g.
        '+NAME+ADDRESS') drove a resolution. Top keys only, with the distinct total."""
        counts = {}
        for e in self.entities.values():
            for r in e["records"]:
                mk = r.get("match_key") or ""
                if mk:
                    counts[mk] = counts.get(mk, 0) + 1
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top = [k for k, _ in items[:20]]
        # Per-key entity lists so Match Keys rows drill down, mirroring
        # bucket_entities on /api/stats and cell_entities on /api/overlap.
        by_key, ent_capped = {k: [] for k in top}, False
        wanted = set(top)
        for e in self.entities.values():
            seen = set()
            for r in e["records"]:
                mk = r.get("match_key") or ""
                if mk in wanted and mk not in seen:
                    seen.add(mk)
                    lst = by_key[mk]
                    if len(lst) < 200:
                        lst.append(
                            {
                                "entity_id": e["entity_id"],
                                "entity_name": e["entity_name"],
                                "record_count": e["record_count"],
                            }
                        )
                    else:
                        ent_capped = True
        return {
            "match_keys": [{"match_key": k, "count": v} for k, v in items[:20]],
            "distinct": len(counts),
            "capped": len(counts) > 20,
            "match_key_entities": by_key,
            "entities_capped": ent_capped,
        }

    def feature_scores(self):
        """Return the pre-computed feature-score distribution (see
        compute_feature_dist). Safe before computation — returns the empty default."""
        return self.feature_dist

    def graph(self):
        node_ids = set(self.entities)
        nodes = list(self.entities.values())
        edges = []
        for (a, b), meta in self.edges.items():
            if a in node_ids and b in node_ids:
                edges.append(
                    {
                        "source_entity_id": a,
                        "target_entity_id": b,
                        "match_key": meta["match_key"],
                        "relationship_type": meta["relationship_type"],
                    }
                )
        return {"nodes": nodes, "edges": edges}

    def merges(self):
        out = [e for e in self.entities.values() if e["record_count"] > 1]
        out.sort(key=lambda e: -e["record_count"])
        return {"entities": out}

    # Name attributes a search tries, in order.
    #
    # Per the Senzing Entity Specification (Name > Feature: NAME): `NAME_ORG` is the
    # organization name attribute, `NAME_FULL` is the "single-field name when type
    # (person vs org) is unknown", and the rule is "use NAME_ORG for organizations;
    # use NAME_FULL only when the type is unknown or only a single field exists".
    #
    # Searching NAME_FULL alone therefore returns **nothing** for an organization,
    # with no error — indistinguishable from "not in the data". On a dataset that is
    # roughly half organizations that silently made half the population
    # unsearchable: "ABSOLUTE DENTAL" returned 0 results while a person name
    # returned a hit immediately, which is the only reason the empty result looked
    # wrong rather than believable.
    SEARCH_NAME_ATTRS = ("NAME_FULL", "NAME_ORG")

    def _search_one(self, engine, flags, attr, query):
        """One `search_by_attributes` call under a single name attribute."""
        attrs = json.dumps({attr: query})
        try:
            raw = engine.search_by_attributes(attrs, flags)
        except TypeError:
            raw = engine.search_by_attributes(attrs, flags, "")
        return json.loads(raw)

    def search(self, engine, flags, query):
        query = (query or "").strip()
        if not query:
            return {"results": []}
        items = []
        tried = []
        failures = []
        for attr in self.SEARCH_NAME_ATTRS:
            tried.append(attr)
            try:
                resp = self._search_one(engine, flags, attr, query)
            except Exception as exc:
                # A failed attempt is an attempt, not the end of the list. This guard
                # was `if not items: return ...`, which is unconditionally true on the
                # *first* attribute — so any error searching NAME_FULL returned before
                # NAME_ORG was ever called and silently reinstated the exact defect
                # INV-164 exists to prevent, this time with an engine message attached
                # pointing at the attribute that could not have matched anyway. Record
                # the failure and carry on: a hit further down the list still wins, and
                # the error is reported only if every candidate is exhausted (INV-190).
                failures.append("%s: %s" % (attr, exc))
                continue
            items.extend(resp.get("RESOLVED_ENTITIES", []))
            if items:
                break  # first attribute that matches wins; no need to pay for the rest
        results = []
        for item in items[:10]:
            ent = item.get("ENTITY", {}).get("RESOLVED_ENTITY", {})
            eid = ent.get("ENTITY_ID")
            match = item.get("MATCH_INFO", {})
            local = self.entities.get(eid, {})
            results.append(
                {
                    "entity_id": eid,
                    "entity_name": ent.get("ENTITY_NAME") or local.get("entity_name", "?"),
                    "record_count": local.get("record_count"),
                    "data_sources": local.get("data_sources", []),
                    "match_key": match.get("MATCH_KEY", ""),
                    "resolution_rule": match.get("ERRULE_CODE", ""),
                }
            )
        # `attributes_tried` lets the UI say what was searched when nothing matched,
        # so an empty result reads as "no match under these attributes" rather than
        # as "this name is not in your data" (INV-115). Failed attempts are listed
        # there too — a candidate that errored was still tried, and the Bootcamper is
        # shown that list.
        out = {"results": results, "attributes_tried": tried}
        # A hit is a hit: a failure behind it is not the Bootcamper's problem. Only when
        # nothing matched anywhere does a failure become the answer — and then it must
        # be reported, or "the engine could not run this" is rendered as the clean
        # no-match "nothing in your data has that name" (INV-115).
        if items == [] and failures:
            out["error"] = "; ".join(failures)
        return out

    def how(self, engine, sz, entity_id):
        """Explain HOW an entity was constructed from its records
        (SzEngine.how_entity_by_entity_id, SZ_HOW_ENTITY_DEFAULT_FLAGS)."""
        try:
            eid = int(entity_id)
        except (TypeError, ValueError):
            return {"error": "invalid entity_id"}
        try:
            raw = engine.how_entity_by_entity_id(eid, sz.SZ_HOW_ENTITY_DEFAULT_FLAGS)
            return {"entity_id": eid, "result": json.loads(raw)}
        except Exception as exc:
            return {"entity_id": eid, "error": "%s: %s" % (type(exc).__name__, exc)}

    def why(self, engine, sz, entity_id):
        """Explain WHY the records in an entity resolved together. Uses
        SzEngine.why_records between two of the entity's constituent records, or
        why_record_in_entity for a single-record entity (both feature-scored)."""
        try:
            eid = int(entity_id)
        except (TypeError, ValueError):
            return {"error": "invalid entity_id"}
        recs = (self.entities.get(eid) or {}).get("records", [])
        try:
            if len(recs) >= 2:
                (d1, r1), (d2, r2) = (
                    (recs[0]["data_source"], recs[0]["record_id"]),
                    (recs[1]["data_source"], recs[1]["record_id"]),
                )
                raw = engine.why_records(d1, r1, d2, r2, sz.SZ_WHY_RECORDS_DEFAULT_FLAGS)
                mode = "why_records"
            elif len(recs) == 1:
                raw = engine.why_record_in_entity(
                    recs[0]["data_source"],
                    recs[0]["record_id"],
                    sz.SZ_WHY_RECORD_IN_ENTITY_DEFAULT_FLAGS,
                )
                mode = "why_record_in_entity"
            else:
                return {"entity_id": eid, "error": "no records known for this entity"}
            return {"entity_id": eid, "mode": mode, "result": json.loads(raw)}
        except Exception as exc:
            return {"entity_id": eid, "error": "%s: %s" % (type(exc).__name__, exc)}

    def compute_feature_dist(self, engine, sz, cap=40):
        """Aggregate feature-score buckets across a **capped** sample of
        multi-record entities (via why_records) so the Feature Scores tab can show
        how tightly resolved records match. Fully guarded: any why failure skips
        that entity and never blocks the model/snapshot build (INV-077). The cap is
        surfaced to the UI (``sampled`` / ``multi_record_total`` / ``capped``) so
        the sample size is never hidden."""
        per_feature = {}   # feature -> {bucket: count}
        multi = [e for e in self.entities.values() if e["record_count"] > 1]
        multi.sort(key=lambda e: -e["record_count"])
        sampled = 0
        for e in multi:
            if sampled >= cap:
                break
            res = self.why(engine, sz, e["entity_id"])
            if not res or res.get("error") or "result" not in res:
                continue
            wr = (res.get("result") or {}).get("WHY_RESULTS") or []
            counted = False
            for w in wr:
                fs = (w.get("MATCH_INFO") or {}).get("FEATURE_SCORES") or {}
                for feat, scores in fs.items():
                    for sc in scores or []:
                        bucket = (sc.get("SCORE_BUCKET") or "").upper()
                        if not bucket:
                            continue
                        per_feature.setdefault(feat, {})
                        per_feature[feat][bucket] = per_feature[feat].get(bucket, 0) + 1
                        counted = True
            if counted:
                sampled += 1
        self.feature_dist = {
            "features": [
                {"feature": f, "buckets": per_feature[f]} for f in sorted(per_feature)
            ],
            "sampled": sampled,
            "multi_record_total": len(multi),
            "capped": len(multi) > cap,
        }
        return self.feature_dist


# --------------------------------------------------------------------------- #
# HTML (single page, D3 v7). Placeholders filled with .replace() to avoid brace
# conflicts with the CSS/JS braces.
# --------------------------------------------------------------------------- #
PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
__D3_SCRIPT__
__DATA_SHIM__
<style>
:root{__ROOT_VARS__}
*{box-sizing:border-box}
body{margin:0;font-family:__FONT_STACK__;color:var(--ink);background:var(--bg)}
header{background:var(--navy);color:#fff;padding:12px 20px;border-bottom:3px solid var(--gold);position:sticky;top:0;z-index:10}
header h1{margin:0;font-size:18px}
.banner{display:flex;gap:10px;flex-wrap:wrap;padding:12px 20px;background:#fff;border-bottom:1px solid var(--line)}
.stat{flex:1;min-width:120px;text-align:center}
.stat .n{font-size:24px;font-weight:700;color:var(--blue)}
.stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.stat .arrow{color:var(--gold);font-weight:700;align-self:center}
nav{display:flex;gap:4px;padding:0 20px;background:#fff;border-bottom:1px solid var(--line)}
nav button{border:none;background:none;padding:10px 14px;font-size:14px;color:var(--muted);cursor:pointer;border-bottom:3px solid transparent}
nav button.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:600}
main{padding:0}
.tab{display:none;padding:16px 20px}
.tab.active{display:block}
#graph-container{position:relative;height:calc(100vh - 175px);min-height:360px;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden;padding:0}
#graph-container svg{width:100%;height:100%;display:block}
.legend{position:absolute;top:10px;right:10px;background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px}
.legend .row{display:flex;align-items:center;gap:6px;margin:2px 0}
.legend .dot{width:12px;height:12px;border-radius:50%}
.node circle{stroke:#fff;stroke-width:1.5px;cursor:pointer}
.node text{font-size:10px;fill:var(--ink);pointer-events:none}
/* Label visibility is driven by a class on the container, set explicitly at
   init -- an unchecked checkbox fires no change event, so the initial state
   cannot be left to the handler (contract: "Init-state note"). */
.hide-node-labels .node text{display:none}
.hide-edge-labels .edge text{display:none}
.gctl{position:absolute;top:10px;left:10px;background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px;z-index:2}
.gctl label{display:flex;align-items:center;gap:6px;margin:2px 0;cursor:pointer}
.gctl .why{color:var(--muted);margin-top:4px;max-width:220px}
.legend .row{cursor:pointer;user-select:none}
.legend .row.off{opacity:.35}
.legend .cnt{color:var(--muted);margin-left:auto;padding-left:8px}
.edge line{stroke:var(--line);stroke-width:1.5px}
.edge text{font-size:9px;fill:var(--muted)}
.tooltip{position:absolute;pointer-events:none;background:var(--navy);color:#fff;padding:6px 9px;border-radius:6px;font-size:12px;opacity:0;max-width:240px}
.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.card h4{margin:0 0 6px;font-size:15px}
.recs{display:flex;gap:10px;flex-wrap:wrap}
.rec{border:1px solid var(--line);border-radius:6px;padding:8px 10px;font-size:12px;min-width:150px;background:var(--bg)}
.chip{display:inline-block;border:1px solid var(--blue);color:var(--blue);background:var(--accent-soft);border-radius:12px;padding:1px 8px;font-size:11px;margin:2px 2px 0 0;font-family:__CODE_FONT__}
.mk span{display:inline-block;border:1px solid var(--gold);background:var(--accent-soft);color:var(--ink);border-radius:4px;padding:0 5px;margin:1px;font-family:__CODE_FONT__;font-size:11px}
#search-in{padding:8px 10px;border:1px solid var(--line);border-radius:6px;font-size:14px;width:min(420px,100%)}
button.probe{border:1px solid var(--line);background:#fff;border-radius:16px;padding:5px 12px;margin:2px;cursor:pointer;font-size:13px}
.muted{color:var(--muted)}
.modal-bg{position:fixed;inset:0;background:rgba(15,13,12,.5);display:none;align-items:center;justify-content:center;z-index:50}
/* Entity-detail dialogs are a primary "wow moment" surface and get the same
   care as the headline tabs: a real header bar separated from the body, a
   circular close control, and a subtle entrance transition (contract:
   "Modal chrome"). */
.modal{background:#fff;border-radius:10px;max-width:420px;width:90%;overflow:hidden;
  box-shadow:0 18px 48px rgba(15,13,12,.28);animation:modal-in .16s ease-out}
@keyframes modal-in{from{opacity:0;transform:translateY(8px) scale(.985)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.modal{animation:none}}
.modal .mhead{background:var(--navy);color:#fff;padding:14px 18px;display:flex;align-items:flex-start;gap:12px}
.modal .mhead h3{margin:0;font-size:16px;color:#fff;flex:1}
.modal .mhead .muted{color:rgba(255,255,255,.72);font-size:12px;margin-top:2px}
.modal .mclose{flex:none;width:28px;height:28px;border-radius:50%;border:none;cursor:pointer;
  background:rgba(255,255,255,.15);color:#fff;font-size:16px;line-height:1;padding:0;margin:0}
.modal .mclose:hover{background:rgba(255,255,255,.28)}
.modal .mbody{padding:16px 18px 18px}
.modal h3{margin:0 0 8px}
.modal button{margin-top:10px;border:none;background:var(--blue);color:#fff;border-radius:6px;padding:6px 12px;cursor:pointer}
.modal.wide{max-width:680px}
.actions{margin-top:8px;display:flex;gap:6px}
.actions button{border:1px solid var(--blue);background:var(--accent-soft);color:var(--blue);border-radius:6px;padding:3px 10px;font-size:12px;cursor:pointer}
.explain pre{max-height:52vh;overflow:auto;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;font-family:__CODE_FONT__;font-size:11px;white-space:pre-wrap;word-break:break-word}
.bucket-list{margin-top:14px}
.bucket-list .rec{cursor:pointer}
.explain h4{margin:12px 0 4px}
.explain details{margin-top:14px}
.explain summary{cursor:pointer;color:var(--muted);font-size:12px}
.legend-note{font-size:12px;color:var(--muted);margin:6px 0 0}
.verdict{border-left:4px solid var(--blue);background:var(--accent-soft);padding:8px 12px;border-radius:0 6px 6px 0;margin:4px 0 10px}
.why-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
.why-table th,.why-table td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.why-table th{background:var(--bg);font-size:10px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
.why-table td.feat{font-weight:600;white-space:nowrap}
.score-bar{height:7px;border-radius:4px;background:var(--line);overflow:hidden;margin-top:4px}
.score-bar>span{display:block;height:100%}
.bucket{display:inline-block;border-radius:10px;padding:1px 8px;font-size:11px;font-weight:600;border:1px solid transparent}
.b-strong{background:#e6f4ea;color:#137333;border-color:#cdebd6}
.b-mid{background:#fef7e0;color:#8a6d00;border-color:#f3e2a6}
.b-weak{background:#fdeee3;color:#a1440a;border-color:#f6cfae}
.b-none{background:#fce8e6;color:#a50e0e;border-color:#f4c7c3}
.step{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;background:#fff}
.step .num{display:inline-block;background:var(--blue);color:#fff;border-radius:50%;width:22px;height:22px;line-height:22px;text-align:center;font-weight:700;font-size:12px;margin-right:6px}
nav{flex-wrap:wrap}
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.kpi{flex:1;min-width:130px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.kpi .n{font-size:26px;font-weight:700;color:var(--blue)}
.kpi .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.section-h{margin:16px 0 6px;font-size:14px}
.heat{border-collapse:collapse;font-size:12px;margin-top:8px}
.heat th,.heat td{border:1px solid var(--line);padding:6px 10px;text-align:center}
.heat th{background:var(--bg);color:var(--muted);font-weight:600}
.heat td.rowh{background:var(--bg);color:var(--muted);font-weight:600;text-align:right}
.heat td.cell{color:var(--ink);font-variant-numeric:tabular-nums}
</style></head>
<body>
<header><h1>__TITLE__</h1></header>
<div class="banner" id="banner"></div>
<nav id="nav"></nav>
<main>
  <section class="tab active" id="tab-graph"><div id="graph-container"><div class="tooltip" id="tt"></div></div></section>
  <section class="tab" id="tab-stats"><div id="hist"></div></section>
  <section class="tab" id="tab-matchkeys"><div id="matchkeys"></div></section>
  <section class="tab" id="tab-features"><div id="features"></div></section>
  <section class="tab" id="tab-overlap"><div id="overlap"></div></section>
  <section class="tab" id="tab-probe">__PROBE_BODY__</section>
</main>
<div class="modal-bg" id="modal-bg" onclick="if(event.target.id==='modal-bg')closeModal()"><div class="modal" id="modal"></div></div>
<script>
// Six tabs. "Record Merges" was removed because Search / Probe's per-entity result is a
// strict superset of it (name, record count, entity match key -- plus per-record match
// keys and feature scores); its one unique capability, browsing all merges with no query,
// moved to the "Show all merged entities" button on that tab. "Relationship Network" was
// removed because it rendered a filtered view of this tab's own /api/graph data; it is now
// the "Show only entities with relationships" mode of Entity Graph. Both per the contract's
// de-duplication rule: when two candidate tabs share their data, they are one tab.
const ALL_TABS=[["graph","Entity Graph"],["stats","Merge Statistics"],["matchkeys","Match Keys"],["features","Feature Scores"],["overlap","Cross-Source"],["probe","Search / Probe"]];
// {source_code: {fill, stroke, cycle}} assigned from the sources actually loaded, so a
// bootcamper's own sources are always distinct. The last-resort literal is for a source
// absent from the model entirely; it is deliberately NOT equal to any assigned color, so
// "unassigned" never masquerades as a real category.
const SRC_COLORS=__SRC_COLORS__;
const UNKNOWN_SRC="#9aa0a6";
function srcStyle(src){return SRC_COLORS[src]||{fill:UNKNOWN_SRC,stroke:"#FFFFFF",stroke_width:null,cycle:0};}
function color(src){return srcStyle(src).fill;}
function srcStroke(src){return srcStyle(src).stroke;}
// The stroke WIDTH decides whether a stroke is drawn at all, and every draw site must key
// on it -- not on `cycle`. `cycle` says which palette wrap a source landed in; it does not
// reach the canvas, and keying on it capped the rendered encoding space at 24 sources while
// the assigned map went on looking collision-free past that.
function srcStrokeW(src){return srcStyle(src).stroke_width||0;}
const CSSV=getComputedStyle(document.documentElement);
function cssv(n,f){var v=CSSV.getPropertyValue(n).trim();return v||f;}
const C_BLUE=cssv('--blue','#F57826'),C_GOLD=cssv('--gold','#FF4E1F'),C_GREEN=cssv('--green','#1D9E75'),C_MUTED=cssv('--muted','#4A4640');
function hexRgb(h){h=(h||"").replace('#','');if(h.length===3)h=h.split('').map(function(c){return c+c;}).join('');var n=parseInt(h,16)||0;return [(n>>16)&255,(n>>8)&255,n&255];}
let STATS=null;
// A tab is shown only when its data exists: 2+ sources for cross-source overlap,
// multi-record entities for match keys / feature scores. The others always apply.
// (The relationship view is no longer a tab -- it is a mode of Entity Graph, gated
// on the same relationships_total > 0 condition inside addGraphControls.)
function tabApplicable(id){const s=STATS||{};
  if(id==="overlap")return (s.data_sources_total||0)>=2;
  if(id==="features")return (s.multi_record_entities||0)>0;
  if(id==="matchkeys")return (s.multi_record_entities||0)>0;
  return true;}
// "all" shows the full entity population; "network" shows only entities connected by a
// relationship, with edges styled by relationship type -- what the removed Relationship
// Network tab rendered. Both modes are served by the same /api/graph payload.
// Above this many entities the full population is a mesh with no practical way to
// locate anything, so Entity Graph opens on the relationship subgraph instead. The
// toggle still switches both ways; only the DEFAULT is scale-aware. Stated in
// visualization-api-reference.md so a server in any language picks the same value.
// (Label defaults are already scale-aware; hiding labels does not thin 4,464 edges.)
const GRAPH_SUBGRAPH_DEFAULT_ABOVE=400;
let graphMode="all";
let graphModeAutoSet=false;
// The live force simulation for the graph tab. Toggling the mode re-enters drawGraph, and
// the previous simulation would otherwise keep ticking against DOM nodes that have been
// removed — wasted work and a source of jank. Stopped before each redraw.
let graphSim=null;
function drawFor(id){
  if(id==="graph")drawGraph();
  else if(id==="stats")drawHist();
  else if(id==="matchkeys")drawMatchKeys();
  else if(id==="features")drawFeatures();
  else if(id==="overlap")drawOverlap();}
function activate(id){
  // Re-activating the tab that is ALREADY active must not redraw it. drawFor() rebuilds
  // the tab, and for the Entity Graph that means a fresh d3.forceSimulation — so
  // re-activating the default tab mid-capture restarts the layout and the screenshot
  // catches the nodes still collapsed in a corner: a plausible-looking empty graph, at
  // exit 0, in the keepsake. Both capture paths hit this (an injected activate('<tab>')
  // and ?tab=<id> deep-linking), and a user clicking the active nav button did too.
  const already=d3.select("#tab-"+id);
  if(!already.empty()&&already.classed("active")&&d3.select("#navbtn-"+id).classed("active"))return;
  d3.selectAll("nav button").classed("active",false);d3.select("#navbtn-"+id).classed("active",true);
  d3.selectAll(".tab").classed("active",false);d3.select("#tab-"+id).classed("active",true);drawFor(id);}
function buildNav(){const nav=d3.select("#nav");nav.html("");
  const tabs=ALL_TABS.filter(function(t){return tabApplicable(t[0]);});
  tabs.forEach(function(t,i){nav.append("button").attr("id","navbtn-"+t[0]).attr("class",i===0?"active":"").text(t[1]).on("click",function(){activate(t[0]);});});
  d3.selectAll(".tab").classed("active",false);if(tabs.length)d3.select("#tab-"+tabs[0][0]).classed("active",true);}
async function getJSON(u){const r=await fetch(u);return r.json();}
async function loadBanner(){const s=await getJSON("/api/stats");
  const items=[["Records Loaded",s.records_total],["Resolved Entities",s.entities_total],["Multi-Record",s.multi_record_entities],["Cross-Source",s.cross_source_entities],["Relationships",s.relationships_total]];
  const b=d3.select("#banner");b.html("");
  items.forEach((it,i)=>{const d=b.append("div").attr("class","stat");d.append("div").attr("class","n").text(it[1]);d.append("div").attr("class","l").text(it[0]);
    if(i<items.length-1)b.append("div").attr("class","arrow").text("→");});}
let graphDrawn=false;
async function drawGraph(){
  const c=document.getElementById("graph-container");const W=c.clientWidth,H=c.clientHeight;
  const g=await getJSON("/api/graph");const box=d3.select("#graph-container");
  d3.select("#graph-container svg").remove();
  d3.select("#graph-container .legend").remove();
  d3.select("#graph-container .empty-note").remove();
  if(graphSim){graphSim.stop();graphSim=null;}
  const links0=g.edges.map(function(e){return {source:e.source_entity_id,target:e.target_entity_id,match_key:e.match_key,rtype:e.relationship_type||"RELATED"};});
  // Scale-aware default, applied once: above the threshold, open on the relationship
  // subgraph rather than the full population. Only when a subgraph actually exists,
  // and never overriding a choice the bootcamper has already made with the toggle.
  if(!graphModeAutoSet){
    graphModeAutoSet=true;
    if(g.nodes.length>GRAPH_SUBGRAPH_DEFAULT_ABOVE&&links0.length){graphMode="network";}
  }
  const network=graphMode==="network";
  // In network mode, keep only entities that a relationship actually connects -- the
  // subgraph the removed Relationship Network tab showed.
  let nodes;
  if(network){
    const connected=new Set();links0.forEach(function(e){connected.add(e.source);connected.add(e.target);});
    nodes=g.nodes.filter(function(n){return connected.has(n.entity_id);}).map(function(n){return Object.assign({},n,{id:n.entity_id});});
  }else{
    nodes=g.nodes.map(function(n){return Object.assign({},n,{id:n.entity_id});});
  }
  if(!nodes.length){
    box.append("div").attr("class","muted empty-note").style("padding","14px")
       .text(network?"No relationships between entities were found in this data.":"No entities to graph.");
    addGraphControls("graph-container",0);
    return;
  }
  // EDGE-KEY MAPPING: forceLink resolves against id via source/target; map before use.
  const idset=new Set(nodes.map(function(n){return n.id;}));
  const links=links0.filter(function(e){return idset.has(e.source)&&idset.has(e.target);});
  const rtypes=Array.from(new Set(links.map(function(e){return e.rtype;})));
  const rcolor=d3.scaleOrdinal().domain(rtypes).range([C_BLUE,C_GOLD,C_GREEN,"#8b5cf6","#ec4899","#0ea5e9"]);
  const svg=box.append("svg").attr("width",W).attr("height",H).attr("viewBox",[0,0,W,H]);
  const root=svg.append("g");
  svg.call(d3.zoom().scaleExtent([0.2,4]).on("zoom",function(ev){root.attr("transform",ev.transform);}));
  const sim=graphSim=d3.forceSimulation(nodes)
    .force("link",d3.forceLink(links).id(function(d){return d.id;}).distance(network?100:90))
    .force("charge",d3.forceManyBody().strength(network?-180:-160))
    .force("center",d3.forceCenter(W/2,H/2))
    .force("collide",d3.forceCollide().radius(function(d){return radius(d)+6;}));
  const edge=root.append("g").selectAll("g").data(links).join("g").attr("class","edge");
  const line=edge.append("line");
  // Relationship-type color plus a dash pattern, so the types stay distinguishable in a
  // monochrome screenshot (contract: pair color with a non-color distinction).
  if(network){
    line.attr("stroke",function(d){return rcolor(d.rtype);}).attr("stroke-width",2)
        .attr("stroke-dasharray",function(d){return rdash(d.rtype);});
  }
  edge.append("text").text(function(d){return d.match_key||"";});
  const node=root.append("g").selectAll("g").data(nodes).join("g").attr("class","node")
    .call(d3.drag().on("start",dstart).on("drag",dragged).on("end",dend))
    .on("click",function(ev,d){openModal(d);})
    .on("mousemove",function(ev,d){const tt=d3.select("#tt");
      tt.style("opacity",1).style("left",(ev.offsetX+14)+"px").style("top",(ev.offsetY+8)+"px")
        .html("<b>"+esc(d.entity_name)+"</b><br>ID "+d.entity_id+" · "+d.record_count+" record(s)<br>"+d.data_sources.join(", "));})
    .on("mouseout",function(){d3.select("#tt").style("opacity",0);});
  node.append("circle").attr("r",radius).attr("fill",function(d){return color(d.data_sources[0]);})
    .attr("stroke",function(d){return srcStrokeW(d.data_sources[0])?srcStroke(d.data_sources[0]):null;})
    .attr("stroke-width",function(d){return srcStrokeW(d.data_sources[0])||null;});
  // Node labels are truncated to fit, so the distinctness rule applies here exactly as it
  // does to match keys (contract: "Defaults at production scale" item 1). Two entities whose
  // names share the first 19 characters -- ACME HOLDINGS INTERNATIONAL LLC vs ...INC, routine
  // in organization data -- would otherwise render as the same string, and the graph would
  // show two nodes nothing distinguishes. Compare the FITTED labels, not the names, and
  // suffix only a genuine collision: two entities that really share a name may legitimately
  // render alike. The full name stays on hover via the group tooltip above.
  const NODE_LABEL_MAX=20;
  const nodeLabel={};
  (function(){const taken={};
    nodes.forEach(function(n){
      const full=n.entity_name||"";
      let lab=full.length>NODE_LABEL_MAX?full.slice(0,NODE_LABEL_MAX-1)+"…":full;
      if(taken[lab]!==undefined&&taken[lab]!==full){
        let k=2;while(taken[lab+" ("+k+")"]!==undefined)k++;
        lab=lab+" ("+k+")";
      }
      taken[lab]=full;
      nodeLabel[n.entity_id]=lab;
    });})();
  node.append("text").attr("dy",function(d){return radius(d)+11;}).attr("text-anchor","middle")
      .text(function(d){return nodeLabel[d.entity_id];})
      .append("title").text(function(d){return d.entity_name||"";});
  sim.on("tick",function(){
    edge.select("line").attr("x1",function(d){return d.source.x;}).attr("y1",function(d){return d.source.y;})
      .attr("x2",function(d){return d.target.x;}).attr("y2",function(d){return d.target.y;});
    edge.select("text").attr("x",function(d){return (d.source.x+d.target.x)/2;}).attr("y",function(d){return (d.source.y+d.target.y)/2;});
    node.attr("transform",function(d){return "translate("+d.x+","+d.y+")";});
  });
  if(network){drawRelationshipLegend(box,links,rtypes,rcolor,edge);}
  else{drawLegend(nodes);}
  addGraphControls("graph-container",nodes.length);
  function dstart(ev,d){if(!ev.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}
  function dragged(ev,d){d.fx=ev.x;d.fy=ev.y;}
  function dend(ev,d){if(!ev.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}
}
// Relationship-type legend with click-to-filter, carried over unchanged from the removed
// Relationship Network tab. Built FROM the drawn edges, so an entry cannot exist without
// matching marks on screen.
function drawRelationshipLegend(box,links,rtypes,rcolor,edge){
  const l=box.append("div").attr("class","legend");
  l.append("div").style("font-weight","600").style("margin-bottom","3px").text("Relationship");
  const rcount={};links.forEach(function(e){rcount[e.rtype]=(rcount[e.rtype]||0)+1;});
  const roff={};
  rtypes.forEach(function(ty){const r=l.append("div").attr("class","row");
    r.append("span").attr("class","dot").style("background",rcolor(ty));
    r.append("span").text(humLevel(ty));
    r.append("span").attr("class","cnt").text(rcount[ty]||0);
    r.attr("title","Show only this relationship type (click again to restore)");
    r.on("click",function(){roff[ty]=!roff[ty];d3.select(this).classed("off",!!roff[ty]);
      const anyOff=rtypes.some(function(x){return roff[x];});
      edge.style("display",function(d){return (!anyOff||!roff[d.rtype])?null:"none";});});});
}
function radius(d){return Math.min(Math.max(8+d.record_count*4,8),40);}
// Above this node count both label sets default OFF. Chosen because a default
// tuned against the 159-record Truth Set produced ~1000 overlapping labels when
// the same app was reused for production-scale data in Module 7 (contract:
// "Scale principle"). Toggles stay available either way.
const LABEL_AUTO_OFF=150;
// Non-color encoding companion to the relationship-type color, so the types
// stay distinguishable in a monochrome recap screenshot and for color-vision
// deficiency (contract: "Pair color with a non-color distinction").
const R_DASH={possibly_same:"",possibly_related:"6,4",disclosed:"2,3",ambiguous:"10,3,2,3"};
function rdash(ty){return R_DASH[String(ty||"").toLowerCase()]||"6,4";}
function addGraphControls(containerId,nodeCount){
  const c=d3.select("#"+containerId);
  c.select(".gctl").remove();
  const auto=nodeCount>LABEL_AUTO_OFF;
  // Apply the initial state to the container explicitly -- do NOT rely on the
  // checkbox change event, which does not fire for an unchecked box at load.
  const el=document.getElementById(containerId);
  el.classList.toggle("hide-node-labels",auto);
  el.classList.toggle("hide-edge-labels",auto);
  const box=c.append("div").attr("class","gctl");
  function toggle(cls,label,on){
    const row=box.append("label");
    const inp=row.append("input").attr("type","checkbox").property("checked",on);
    row.append("span").text(label);
    inp.on("change",function(){el.classList.toggle(cls,!this.checked);});}
  toggle("hide-node-labels","Entity name labels",!auto);
  toggle("hide-edge-labels","Match key labels",!auto);
  // Mode switch: the full entity population, or only the entities a relationship
  // connects. Replaces the standalone Relationship Network tab, and is shown only when
  // there are relationships to see — the same condition that used to gate that tab.
  if(((STATS||{}).relationships_total||0)>0){
    const row=box.append("label");
    const inp=row.append("input").attr("type","checkbox").attr("id","graph-network-only")
                 .property("checked",graphMode==="network");
    row.append("span").text("Show only entities with relationships");
    inp.on("change",function(){graphMode=this.checked?"network":"all";drawGraph();});
  }
  if(auto)box.append("div").attr("class","why")
    .text("Labels hidden — "+nodeCount+" entities would overlap. Use the toggles to show them.");
  // Same reasoning as the label note: without it the bootcamper reads a default as
  // their data, and concludes the graph is showing everything there is.
  if(graphMode==="network"&&(STATS||{}).entities_total>GRAPH_SUBGRAPH_DEFAULT_ABOVE)
    box.append("div").attr("class","why")
      .text("Showing the "+nodeCount+" entities that have relationships, of "+
            STATS.entities_total+" total — the full population is too dense to read at this "+
            "scale. Uncheck the toggle above to show them all.");}
// Built FROM the rendered nodes, never from a static color config: a legend
// entry then cannot exist without matching marks on screen, which is what makes
// "the legend shows colors that appear nowhere in the graph" impossible.
// Clicking an entry filters the view and toggles back.
function drawLegend(nodes){d3.select("#graph-container .legend").remove();
  const counts={};(nodes||[]).forEach(function(n){(n.data_sources||[]).forEach(function(s){counts[s]=(counts[s]||0)+1;});});
  const srcs=Object.keys(counts).sort();
  if(!srcs.length)return;
  const off={};
  const l=d3.select("#graph-container").append("div").attr("class","legend");
  srcs.forEach(function(s){const r=l.append("div").attr("class","row");
    r.append("span").attr("class","dot").style("background",color(s))
      // Same expression as the node's stroke, so the swatch and the node cannot disagree
      // about a source's encoding -- including its WIDTH, which is a channel above 24
      // sources.
      .style("box-shadow",srcStrokeW(s)?("inset 0 0 0 "+srcStrokeW(s)+"px "+srcStroke(s)):null);
    r.append("span").text(s);
    r.append("span").attr("class","cnt").text(counts[s]);
    r.attr("title","Show only "+s+" (click again to restore)");
    r.on("click",function(){off[s]=!off[s];d3.select(this).classed("off",!!off[s]);
      const anyOff=srcs.some(function(x){return off[x];});
      d3.selectAll("#graph-container .node").style("display",function(d){
        if(!anyOff)return null;
        const keep=(d.data_sources||[]).some(function(x){return !off[x];});
        return keep?null:"none";});});});}
function openModal(d){const m=d3.select("#modal");document.getElementById("modal").className="modal";
  const body="<p><b>Data sources:</b> "+esc(d.data_sources.join(", "))+"<br><b>Records:</b> "+d.record_count+"</p>"+
    "<div id='node-actions'></div>";
  m.html(modalShell(d.entity_name,"Entity "+d.entity_id,body));
  // Same three actions as every other entity surface -- the graph node modal is
  // not an exception (contract: "Per-entity actions").
  addEntityActions(d3.select("#node-actions"),d.entity_id,d.entity_name);
  document.getElementById("modal-bg").style.display="flex";}
function closeModal(){document.getElementById("modal-bg").style.display="none";}
// Shared modal chrome: header bar (title + subtitle + circular close) and a body
// wrapper. Every entity dialog -- Records, Why?, How? -- goes through this, so
// they cannot drift apart visually.
function modalShell(title,subtitle,bodyHtml){
  return "<div class='mhead'><div><h3>"+esc(title)+"</h3>"+
    (subtitle?"<div class='muted'>"+esc(subtitle)+"</div>":"")+
    "</div><button class='mclose' onclick='closeModal()' title='Close' aria-label='Close'>&times;</button></div>"+
    "<div class='mbody'>"+bodyHtml+"</div>";}
// The canonical per-entity action set (contract: "Per-entity actions"). ONE
// renderer, invoked from every surface that shows an entity — graph node modal,
// the merged-entity cards on Search / Probe, every aggregate drill-down, and
// search results. Adding a
// button here reaches all of them; that is the point. Wiring actions per
// code-path is how surfaces previously shipped with different subsets.
function addEntityActions(sel,eid,name){if(eid===undefined||eid===null)return;
  const a=sel.append("div").attr("class","actions");
  a.append("button").attr("title","Show the records that make up this entity").text("Records").on("click",function(){showRecords(eid,name);});
  a.append("button").attr("title","Why did these records resolve together?").text("Why?").on("click",function(){explain("why",eid,name);});
  a.append("button").attr("title","How was this entity constructed?").text("How?").on("click",function(){explain("how",eid,name);});}
// Renders a list of entities with the full action set — shared by every
// aggregate drill-down (histogram buckets, cross-source cells, match-key rows)
// and by the largest-entities list, so all of them behave identically.
function renderEntityList(box,entities,emptyMsg){
  if(!entities||!entities.length){box.append("p").attr("class","muted").text(emptyMsg||"No entities.");return;}
  entities.forEach(function(e){
    const row=box.append("div").attr("class","card");
    row.append("h4").text(e.entity_name||("Entity "+e.entity_id));
    const meta=[];
    if(e.record_count!==undefined)meta.push(e.record_count+" record"+(e.record_count===1?"":"s"));
    if(e.data_sources&&e.data_sources.length)meta.push(e.data_sources.join(" + "));
    meta.push("Entity "+e.entity_id);
    row.append("div").attr("class","muted").text(meta.join(" · "));
    addEntityActions(row,e.entity_id,e.entity_name);});}
async function showRecords(eid,name){const m=d3.select("#modal");
  document.getElementById("modal").className="modal wide explain";
  const sub=(name||"")+" · Entity "+eid;
  m.html(modalShell("Records in this entity",sub,"<p class='muted'>Loading…</p>"));
  document.getElementById("modal-bg").style.display="flex";
  let data;try{data=await getJSON("/api/records?entity_id="+encodeURIComponent(eid));}catch(e){data={error:String(e)};}
  let body="";
  if(data&&data.error){body="<p class='muted'>"+esc(data.error)+"</p>";}
  else{const recs=(data&&data.records)||[];
    if(!recs.length){body="<p class='muted'>No records returned for this entity.</p>";}
    // Columns come from the fields the endpoint actually returned, never from a fixed
    // list: this server's /api/records carries data_source/record_id/match_key, so a
    // hardcoded Name/Address/Phone header rendered three empty columns for every row
    // and read as missing data rather than as a payload that never had those fields.
    else{const cols=[["match_key","Match key"],["name","Name"],["address","Address"],["phone","Phone"]]
        .filter(function(c){return recs.some(function(r){return r[c[0]];});});
      body="<table class='tbl'><thead><tr><th>Source</th><th>Record</th>"+
        cols.map(function(c){return "<th>"+esc(c[1])+"</th>";}).join("")+"</tr></thead><tbody>";
      recs.forEach(function(r){body+="<tr><td>"+esc(r.data_source)+"</td><td>"+esc(r.record_id)+"</td>"+
        cols.map(function(c){return "<td>"+esc(r[c[0]]||"")+"</td>";}).join("")+"</tr>";});
      body+="</tbody></table>";}}
  m.html(modalShell("Records in this entity",sub,body));}
function explainTitle(kind){return kind==="why"?"Why did these records resolve together?":"How was this entity built?";}
async function explain(kind,eid,name){const m=d3.select("#modal");
  document.getElementById("modal").className="modal wide explain";
  const sub=(name||"")+" · Entity "+eid;
  m.html(modalShell(explainTitle(kind),sub,"<p class='muted'>Loading…</p>"));
  document.getElementById("modal-bg").style.display="flex";
  let data;try{data=await getJSON("/api/"+kind+"?entity_id="+encodeURIComponent(eid));}catch(e){data={error:String(e)};}
  let body="";
  if(data&&data.error){body="<p class='muted'>"+esc(data.error)+"</p>";}
  else{body=(kind==="why"?renderWhy(data):renderHow(data));
    body+="<details><summary>Show the raw Senzing response (JSON)</summary><pre>"+esc(JSON.stringify(data&&data.result!==undefined?data.result:data,null,2))+"</pre></details>";}
  m.html(modalShell(explainTitle(kind),sub,body));}
function mkChips(mk){return (mk||"").split(/(?=[+-])/).filter(function(p){return p;})
  .map(function(p){return "<span class='chip'>"+esc(p)+"</span>";}).join("")||"<span class='muted'>(none)</span>";}
function humLevel(l){return ({RESOLVED:"the same entity",POSSIBLY_SAME:"possibly the same entity",
  POSSIBLY_RELATED:"possibly related",DISCLOSED_RELATION:"a disclosed relationship",
  NO_RELATION:"not related"})[l]||(l?l.toLowerCase().replace(/_/g," "):"related");}
function bucketMeta(b){b=(b||"").toUpperCase();
  if(b==="SAME")return ["b-strong","#137333","Same"];
  if(b==="CLOSE")return ["b-strong","#137333","Close"];
  if(b==="LIKELY")return ["b-mid","#8a6d00","Likely"];
  if(b==="PLAUSIBLE")return ["b-weak","#a1440a","Plausible"];
  if(b==="NO_CHANCE"||b==="UNLIKELY")return ["b-none","#a50e0e","No match"];
  return ["b-mid","#8a6d00",b||"—"];}
function renderWhy(data){const wr=((data.result||{}).WHY_RESULTS)||[];
  if(!wr.length)return "<p class='muted'>Senzing returned no comparison detail for these records.</p>";
  const mi=wr[0].MATCH_INFO||{};const key=mi.WHY_KEY||mi.MATCH_KEY||"";const rule=mi.WHY_ERRULE_CODE||mi.ERRULE_CODE||"";const level=mi.MATCH_LEVEL_CODE||"";
  let h="<div class='verdict'>Senzing considers these records <b>"+esc(humLevel(level))+"</b> — on match key "+mkChips(key)+(rule?" (rule <code>"+esc(rule)+"</code>)":"")+".</div>";
  const fs=mi.FEATURE_SCORES||{};const feats=Object.keys(fs);
  if(feats.length){
    h+="<h4>Feature-by-feature comparison</h4>";
    h+="<table class='why-table'><thead><tr><th>Feature</th><th>Record A</th><th>Record B</th><th>How well it matched</th></tr></thead><tbody>";
    feats.forEach(function(ft){(fs[ft]||[]).forEach(function(sc){
      const bm=bucketMeta(sc.SCORE_BUCKET);const sv=(sc.SCORE===0||sc.SCORE)?sc.SCORE:"";
      h+="<tr><td class='feat'>"+esc(ft)+"</td><td>"+esc(sc.INBOUND_FEAT_DESC||"")+"</td><td>"+esc(sc.CANDIDATE_FEAT_DESC||"")+"</td>"+
        "<td><span class='bucket "+bm[0]+"'>"+esc(bm[2])+(sv!==""?" · "+sv:"")+"</span>"+
        (sv!==""?"<div class='score-bar'><span style='width:"+Math.max(3,Math.min(100,sv))+"%;background:"+bm[1]+"'></span></div>":"")+"</td></tr>";
    });});
    h+="</tbody></table><p class='legend-note'>Each row compares one feature across the two records. The score (0–100) and its bucket show how strongly that feature agreed — green = strong, amber = likely, orange = plausible, red = no match.</p>";
  }
  return h;}
function _recordChips(members){var out=[];(members||[]).forEach(function(mb){(mb.RECORDS||[]).forEach(function(r){
  out.push("<span class='chip'>"+esc((r.DATA_SOURCE||"?")+":"+(r.RECORD_ID||"?"))+"</span>");});});
  return out.join("")||"<span class='muted'>—</span>";}
function renderHow(data){const hr=(data.result||{}).HOW_RESULTS||{};const steps=hr.RESOLUTION_STEPS||[];
  if(steps.length){
    let h="<div class='verdict'>Senzing built this entity in <b>"+steps.length+"</b> step(s), each merging two groups of records.</div>";
    steps.forEach(function(st,i){const mi=st.MATCH_INFO||{};const mk=mi.MATCH_KEY||"";const rule=mi.ERRULE_CODE||"";
      const v1=st.VIRTUAL_ENTITY_1||{};const v2=st.VIRTUAL_ENTITY_2||{};
      h+="<div class='step'><div><span class='num'>"+(st.STEP||(i+1))+"</span><b>Merged on</b> "+mkChips(mk)+(rule?" · <code>"+esc(rule)+"</code>":"")+"</div>"+
        "<div class='recs' style='margin-top:8px'><div class='rec'><b>Group A</b><br>"+_recordChips(v1.MEMBER_RECORDS)+"</div>"+
        "<div class='rec'><b>Group B</b><br>"+_recordChips(v2.MEMBER_RECORDS)+"</div></div></div>";});
    return h;}
  const ve=((hr.FINAL_STATE||{}).VIRTUAL_ENTITIES)||[];
  var members=[];ve.forEach(function(v){(v.MEMBER_RECORDS||[]).forEach(function(m){members.push(m);});});
  var n=0;members.forEach(function(m){n+=((m.RECORDS||[]).length);});
  return "<div class='verdict'>These records resolved <b>directly</b> into one entity — Senzing found them consistent enough to merge with no intermediate steps.</div>"+
    "<h4>"+n+" record"+(n===1?"":"s")+" in this entity</h4>"+
    "<div class='recs'><div class='rec' style='min-width:auto'>"+_recordChips(members)+"</div></div>";}
async function drawHist(){const s=await getJSON("/api/stats");const box=d3.select("#hist");box.html("");
  box.append("p").html("<b>"+s.records_total+"</b> records collapsed into <b>"+s.entities_total+"</b> entities, including <b>"+s.multi_record_entities+"</b> multi-record entities.");
  box.append("p").attr("class","muted").text("Click a bar to list the entities in that bucket.");
  const data=[["1 record","1"],["2 records","2"],["3 records","3"],["4+ records","4+"]]
    .map(function(z){return {label:z[0],key:z[1],n:s.histogram[z[1]]||0};});
  const W=Math.min(720,box.node().clientWidth),H=300,m={t:20,r:10,b:40,l:44};
  const svg=box.append("svg").attr("width",W).attr("height",H);
  const x=d3.scaleBand().domain(data.map(function(d){return d.label;})).range([m.l,W-m.r]).padding(0.25);
  const y=d3.scaleLinear().domain([0,d3.max(data,function(d){return d.n;})||1]).nice().range([H-m.b,m.t]);
  svg.append("g").attr("transform","translate(0,"+(H-m.b)+")").call(d3.axisBottom(x));
  svg.append("g").attr("transform","translate("+m.l+",0)").call(d3.axisLeft(y).ticks(5));
  svg.selectAll("rect").data(data).join("rect").attr("x",function(d){return x(d.label);}).attr("y",function(d){return y(d.n);})
    .attr("width",x.bandwidth()).attr("height",function(d){return y(0)-y(d.n);}).attr("rx",4).style("cursor","pointer")
    .attr("fill",function(d,i){return i===0?"__ACCENT__":"__ACCENT_HOT__";})
    .on("click",function(ev,d){showBucket(s,d.key,d.label);});
  svg.selectAll("text.v").data(data).join("text").attr("class","v").attr("x",function(d){return x(d.label)+x.bandwidth()/2;})
    .attr("y",function(d){return y(d.n)-6;}).attr("text-anchor","middle").attr("font-size",13).attr("font-weight",600).text(function(d){return d.n;});
  box.append("div").attr("id","bucket-list").attr("class","bucket-list");
  // The largest resolved entities — formerly the Results Dashboard's only
  // unique content, folded in here when that duplicate tab was removed
  // (contract: "De-duplication (required)"). Headline counts stay in the page
  // summary strip and are deliberately NOT repeated on this tab.
  box.append("h3").attr("class","section-h").text("Largest resolved entities");
  const samp=s.sample_entities||[];
  const sbox=box.append("div");
  renderEntityList(sbox,samp,"No multi-record entities.");}
function showBucket(s,key,label){const box=d3.select("#bucket-list");if(box.empty())return;box.html("");
  const list=(s.bucket_entities&&s.bucket_entities[key])||[];
  const total=(s.histogram&&s.histogram[key])||list.length;
  box.append("h4").text(label+" — "+total+(total===1?" entity":" entities"));
  renderEntityList(box,list,"No entities in this bucket.");
  if(total>list.length)box.append("p").attr("class","muted").text("Showing first "+list.length+" of "+total+".");}
async function doSearch(){const q=document.getElementById("search-in").value;const box=d3.select("#results");box.html("<p class='muted'>Searching…</p>");
  const r=await getJSON("/api/search?q="+encodeURIComponent(q));box.html("");
  // Name what was searched, so an empty result reads as "no match under these
  // attributes" and not as "this name is not in your data" (INV-115).
  if(!r.results||!r.results.length){const tried=(r.attributes_tried||[]).join(" then ");
    const how=tried?("a "+tried+" search for "):"";
    box.append("p").attr("class","muted").text(r.error?("Search could not run: "+r.error)
      :("No entity matched "+how+'"'+q+'".'));return;}
  r.results.forEach(function(e){const card=box.append("div").attr("class","card");
    card.append("h4").text(e.entity_name);
    card.append("div").attr("class","muted").text("Entity "+e.entity_id+" · "+(e.record_count||"?")+" record(s) · "+(e.data_sources||[]).join(", "));
    if(e.match_key){const mk=card.append("div").attr("class","mk");e.match_key.split(/(?=[+-])/).forEach(function(p){if(p)mk.append("span").text(p);});}
    if(e.resolution_rule)card.append("div").append("code").text(e.resolution_rule);
    addEntityActions(card,e.entity_id,e.entity_name);});}
async function loadProbes(){const m=await getJSON("/api/merges");const box=d3.select("#probe-btns");box.html("");
  // The example chips drive the live search box. The static snapshot has none, so they would be
  // dead controls there — offer only the browse, which needs no engine.
  const live=!!document.getElementById("search-in");
  // Chips MUST be verified to return at least one match before being offered: a hint
  // that finds nothing is worse than no hint, and that is exactly what a chip named
  // after an organization did while search tried NAME_FULL only. Verify against the
  // live engine — the same path the click will take — and drop any that come back
  // empty rather than shipping a dead control.
  // Verified concurrently rather than one at a time: nothing about the check is
  // order-dependent, and a serial loop puts up to ten live engine round-trips in front
  // of the first paint of the app. Order and the six-chip cap are reapplied to the
  // results, so the chips offered are identical to the serial version's — only the
  // waiting is gone. The trade is that all candidates are now searched instead of
  // stopping at the sixth hit: the worst case (ten) is what it always was, the typical
  // case costs a few more searches, and both happen in one round-trip.
  if(live){const cands=(m.entities||[]).slice(0,10).filter(function(e){return e.entity_name;});
    // Each candidate catches its own failure, so one rejected search drops one chip
    // rather than rejecting the batch and taking every chip down with it.
    const verdicts=await Promise.all(cands.map(function(e){
      return getJSON("/api/search?q="+encodeURIComponent(e.entity_name))
        .then(function(r){const hit=!!(r&&r.results&&r.results.length);
          if(!hit)console.warn("dropped example chip (no match): "+e.entity_name);
          return hit;})
        .catch(function(err){console.warn("dropped example chip (search failed): "+e.entity_name);return false;});}));
    const good=cands.filter(function(e,i){return verdicts[i];}).slice(0,6);
    good.forEach(function(e){box.append("button").attr("class","probe").text(e.entity_name)
      .on("click",function(){document.getElementById("search-in").value=e.entity_name;doSearch();});});}
  // The one capability the removed Record Merges tab uniquely had: browse every merged
  // entity with no query. Search / Probe otherwise shows a strict superset per entity,
  // so this is what keeps the removal lossless rather than a trade.
  if((m.entities||[]).length){
    box.append("button").attr("class","probe").attr("id","show-all-merges")
       .text("Show all merged entities ("+m.entities.length+")")
       .on("click",function(){showAllMerges(m.entities);});
  }}
// Lists every multi-record entity, no query needed. Same per-entity actions as a search
// result, so the entity surfaces stay consistent (contract: per-entity actions everywhere).
function showAllMerges(entities){
  const box=d3.select("#results");box.html("");
  const si=document.getElementById("search-in");
  if(si)si.value="";
  if(!entities.length){box.append("p").attr("class","muted").text("No multi-record entities.");return;}
  box.append("p").attr("class","muted")
     .text("All "+entities.length+" merged entities. Search above to see per-record match keys and feature scores for one of them.");
  entities.forEach(function(e){const card=box.append("div").attr("class","card");
    card.append("h4").text(e.entity_name+"  ");
    card.select("h4").append("span").attr("class","chip").text((e.data_sources||[]).join(" + "));
    const mk=(e.records||[]).map(function(r){return r.match_key;}).filter(function(x){return x;})[0]||"";
    card.append("div").attr("class","muted").text(e.record_count+" records · Entity "+e.entity_id);
    // mkChips returns one HTML string, already escaped per chip — set it, do not iterate it.
    if(mk)card.append("div").html(mkChips(mk));
    addEntityActions(card,e.entity_id,e.entity_name);});}
// Cross-Source overlap heatmap: entities shared between each pair of data sources.
async function drawOverlap(){const o=await getJSON("/api/overlap");const box=d3.select("#overlap");box.html("");
  const src=o.sources||[],m=o.matrix||[];
  box.append("p").html("Each cell is the number of resolved entities that appear in <b>both</b> data sources; the diagonal is the entities present in that source.");
  if(src.length<2){box.append("p").attr("class","muted").text("Cross-source overlap needs at least two data sources.");return;}
  let max=1;for(let i=0;i<m.length;i++)for(let j=0;j<m.length;j++){if(i!==j&&m[i][j]>max)max=m[i][j];}
  const rgb=hexRgb(C_BLUE);
  const t=box.append("table").attr("class","heat");
  const head=t.append("thead").append("tr");head.append("th").text("");
  src.forEach(function(s){head.append("th").text(s);});
  const tb=t.append("tbody");
  src.forEach(function(s,i){const tr=tb.append("tr");tr.append("td").attr("class","rowh").text(s);
    src.forEach(function(_,j){const v=(m[i]&&m[i][j])||0;const td=tr.append("td").attr("class","cell").text(v);
      if(i===j){td.style("background","var(--bg)").style("font-weight","600");}
      else if(v>0){const a=0.15+0.85*v/max;td.style("background","rgba("+rgb[0]+","+rgb[1]+","+rgb[2]+","+a.toFixed(3)+")");if(a>0.55)td.style("color","#fff");}
      // Every aggregate drills down (contract: "Drill-down on every aggregate
      // view"). Cross-Source was previously the one dead end.
      if(v>0){td.style("cursor","pointer").attr("title","Show these entities")
        .on("click",function(){showOverlapCell(o,i,j,src[i],src[j]);});}
    });});
  box.append("div").attr("id","overlap-list");
  if(o.cell_capped)box.append("p").attr("class","muted").text("Entity lists are capped; the cell counts remain exact.");
}
function showOverlapCell(o,i,j,si,sj){const box=d3.select("#overlap-list");if(box.empty())return;box.html("");
  const key=Math.min(i,j)+","+Math.max(i,j);
  const list=(o.cell_entities&&o.cell_entities[key])||[];
  const total=(o.matrix&&o.matrix[i]&&o.matrix[i][j])||list.length;
  box.append("h4").text(i===j?(si+" — "+total+(total===1?" entity":" entities"))
    :(si+" ∩ "+sj+" — "+total+(total===1?" shared entity":" shared entities")));
  renderEntityList(box,list,"No entities in this cell.");
  if(total>list.length)box.append("p").attr("class","muted").text("Showing first "+list.length+" of "+total+".");}
// Match Keys: which feature combinations drove the most resolutions.
async function drawMatchKeys(){const d=await getJSON("/api/matchkeys");const box=d3.select("#matchkeys");box.html("");
  const items=d.match_keys||[];
  box.append("p").html("Which feature combinations (match keys) drove the most resolutions across your data.");
  if(!items.length){box.append("p").attr("class","muted").text("No match keys were recorded for the resolved records.");return;}
  // Gutter sized from the data, then labels fitted to it. Real match keys run to
  // 70+ chars ("+NAME+ADDRESS+NATIONAL_ID+OTHER_ID+REGISTRATION_DATE+..."), and a
  // fixed 190px gutter with text-anchor:end pushed the head of every long key off
  // the left edge of the SVG -- so the four highest bars all rendered as
  // "...ISTRATION_COUNTRY+LEI_NUMBER" and could not be told apart. Counts were
  // right, labels useless, and the chart looked fine.
  const W=Math.min(720,box.node().clientWidth),barh=26;
  const longest=d3.max(items,function(z){return (z.match_key||"").length;})||0;
  const gutter=Math.max(150,Math.min(320,longest*5.9+14));
  const mm={t:6,r:44,b:6,l:Math.min(gutter,W*0.55)},H=mm.t+mm.b+items.length*barh;
  // MIDDLE-ellipsize, never left-trim. Right-trimming alone is not enough: real
  // keys are "+A+B+C..." sequences that often share a long prefix and differ only
  // in the last segment, so head-only truncation renders the top bars identically
  // -- the same unreadable chart, just failing from the other end. Keeping both
  // ends makes keys that differ at either end distinguishable.
  const maxChars=Math.max(8,Math.floor((mm.l-10)/5.9));
  function fitKey(k){k=k||"";if(k.length<=maxChars)return k;
    const tail=Math.max(6,Math.floor((maxChars-1)*0.5)),head=maxChars-1-tail;
    return k.slice(0,head)+"…"+k.slice(k.length-tail);}
  // The requirement is DISTINCTNESS, not the ellipsis strategy: no two rendered
  // labels may be identical unless their underlying values are. Middle-ellipsis
  // reduces collisions but cannot prevent them -- two keys sharing a long head AND
  // a long tail, differing only in the elided middle, still render identically, and
  // the top bars again cannot be told apart. So check, and disambiguate the ones
  // that collide with a positional suffix; the full value stays on hover either way.
  const fitted=items.map(function(z){return fitKey(z.match_key);});
  const seen={};
  fitted.forEach(function(label,i){
    if(seen[label]===undefined){seen[label]=i;return;}
    // Only a real collision (different source values) needs disambiguating.
    if(items[seen[label]].match_key===items[i].match_key)return;
    fitted[i]=label+" ("+(i+1)+")";
  });
  function labelFor(i){return fitted[i];}
  const svg=box.append("svg").attr("width",W).attr("height",H);
  const x=d3.scaleLinear().domain([0,d3.max(items,function(z){return z.count;})||1]).range([mm.l,W-mm.r]);
  const y=d3.scaleBand().domain(items.map(function(z){return z.match_key;})).range([mm.t,H-mm.b]).padding(0.2);
  svg.selectAll("rect").data(items).join("rect").attr("x",mm.l).attr("y",function(z){return y(z.match_key);})
    .attr("width",function(z){return Math.max(0,x(z.count)-mm.l);}).attr("height",y.bandwidth()).attr("rx",3).attr("fill",C_BLUE);
  svg.selectAll("text.k").data(items).join("text").attr("class","k").attr("x",mm.l-8).attr("y",function(z){return y(z.match_key)+y.bandwidth()/2;})
    .attr("text-anchor","end").attr("dominant-baseline","middle").attr("font-size",11).attr("font-family","__CODE_FONT__").text(function(z,i){return labelFor(i);})
    .append("title").text(function(z){return z.match_key;});
  svg.selectAll("text.c").data(items).join("text").attr("class","c").attr("x",function(z){return x(z.count)+5;}).attr("y",function(z){return y(z.match_key)+y.bandwidth()/2;})
    .attr("dominant-baseline","middle").attr("font-size",11).attr("font-weight",600).text(function(z){return z.count;});
  if(d.capped)box.append("p").attr("class","muted").text("Showing the top "+items.length+" of "+d.distinct+" distinct match keys.");
  // Clickable rows -> the entities carrying that match key (contract:
  // "Drill-down on every aggregate view"). Match Keys was the last dead end.
  svg.selectAll("rect").style("cursor","pointer").append("title").text(function(z){return z.match_key+" — click to show the entities with this match key";});
  svg.selectAll("rect").on("click",function(ev,z){showMatchKey(d,z.match_key,z.count);});
  box.append("div").attr("id","matchkey-list");
  if(d.entities_capped)box.append("p").attr("class","muted").text("Entity lists are capped; the counts remain exact.");
}
function showMatchKey(d,key,count){const box=d3.select("#matchkey-list");if(box.empty())return;box.html("");
  const list=(d.match_key_entities&&d.match_key_entities[key])||[];
  box.append("h4").text(key+" — "+count+(count===1?" record":" records"));
  renderEntityList(box,list,"No entities recorded for this match key.");
  if(list.length&&count>list.length)box.append("p").attr("class","muted").text("Showing first "+list.length+" entities.");}
// Feature Scores: how tightly each feature agreed across resolved records
// (from a capped why_records sample; the sample size is always shown).
async function drawFeatures(){const d=await getJSON("/api/features");const box=d3.select("#features");box.html("");
  const feats=d.features||[];
  box.append("p").html("How tightly each feature agreed across resolved records — greener means stronger agreement.");
  if(!feats.length){box.append("p").attr("class","muted").text("Feature-score details come from the live server; none were sampled (no multi-record entities, or the sample is unavailable in this snapshot).");return;}
  const order=["SAME","CLOSE","PLUS","LIKELY","PLAUSIBLE","UNLIKELY","NO_CHANCE"];
  const bcolor={SAME:"#137333",CLOSE:"#137333",PLUS:C_GREEN,LIKELY:"#8a6d00",PLAUSIBLE:"#a1440a",UNLIKELY:"#a50e0e",NO_CHANCE:"#a50e0e"};
  const rows=feats.map(function(f){const b=f.buckets||{};const total=Object.keys(b).reduce(function(s,k){return s+b[k];},0)||1;return {feature:f.feature,buckets:b,total:total};});
  const W=Math.min(720,box.node().clientWidth),barh=32,mm={t:6,r:10,b:6,l:130},H=mm.t+mm.b+rows.length*barh;
  const x=d3.scaleLinear().domain([0,1]).range([mm.l,W-mm.r]);
  const y=d3.scaleBand().domain(rows.map(function(z){return z.feature;})).range([mm.t,H-mm.b]).padding(0.25);
  const svg=box.append("svg").attr("width",W).attr("height",H);
  rows.forEach(function(r){let acc=0;const keys=order.filter(function(k){return r.buckets[k];}).concat(Object.keys(r.buckets).filter(function(k){return order.indexOf(k)<0;}));
    keys.forEach(function(k){const frac=r.buckets[k]/r.total;svg.append("rect").attr("x",x(acc)).attr("y",y(r.feature)).attr("width",Math.max(0,x(acc+frac)-x(acc))).attr("height",y.bandwidth()).attr("fill",bcolor[k]||C_MUTED).append("title").text(k+": "+r.buckets[k]);acc+=frac;});
    svg.append("text").attr("x",mm.l-8).attr("y",y(r.feature)+y.bandwidth()/2).attr("text-anchor","end").attr("dominant-baseline","middle").attr("font-size",12).attr("font-weight",600).text(r.feature);});
  box.append("p").attr("class","muted").text("Based on "+d.sampled+" of "+d.multi_record_total+" multi-record entities"+(d.capped?" (sampled to bound cost).":"."));
}
function esc(s){return (s||"").replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
// Deep-link support: ?tab=<id> opens that tab, ?q=<text> runs a search on Search /
// Probe (defaulting the tab to probe). Makes any view of the app a shareable URL, and
// is how the screenshot helper captures one image per tab — including Search / Probe
// showing real results, which the static snapshot cannot do (it has no engine).
function applyDeepLink(){
  var p=new URLSearchParams(location.search||"");
  var tab=p.get("tab"), q=p.get("q");
  if(q!==null&&!tab)tab="probe";
  if(tab&&tabApplicable(tab)&&document.getElementById("tab-"+tab)&&document.getElementById("navbtn-"+tab))activate(tab);
  if(q!==null){var box=document.getElementById("search-in");if(box){box.value=q;doSearch();}}
}
async function init(){STATS=await getJSON("/api/stats");await loadBanner();buildNav();drawGraph();loadProbes();applyDeepLink();}
init();
window.addEventListener("resize",function(){
  if(d3.select("#tab-graph").classed("active"))drawGraph();});
</script></body></html>
"""


# The live Search/Probe tab: an interactive search box backed by /api/search.
PROBE_BODY_LIVE = (
    '<div style="margin-bottom:10px">'
    '<input id="search-in" placeholder="Search a name (e.g. Robert Smith)"> '
    '<button class="probe" onclick="doSearch()">Search</button></div>'
    '<div id="probe-btns"></div><div id="results"></div>'
)


def _d3_script():
    """Return an inline <script> carrying the vendored D3, so the visualization
    renders with no network access. Fall back to the CDN tag only if the vendored
    asset is missing."""
    vendored = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "vendor", "d3.v7.min.js"
    )
    try:
        with open(vendored, encoding="utf-8") as fh:
            return "<script>" + fh.read() + "</script>"
    except OSError:
        return '<script src="https://d3js.org/d3.v7.min.js"></script>'


def render_page(title, data_shim="", probe_body=None, sources=None):
    # Replace D3 and the data shim LAST so their contents are never rescanned for
    # the other placeholders.
    root_vars = (
        "--navy:%(dark)s;--blue:%(accent)s;--gold:%(accent_hot)s;--ink:%(ink)s;"
        "--muted:%(muted)s;--line:%(line)s;--bg:%(bg)s;--accent-soft:%(accent_soft)s;"
        "--green:%(green)s" % _BRAND
    )
    return (
        PAGE.replace("__TITLE__", title)
        .replace("__PROBE_BODY__", probe_body if probe_body is not None else PROBE_BODY_LIVE)
        .replace("__ROOT_VARS__", root_vars)
        .replace("__FONT_STACK__", _BRAND["font"])
        .replace("__CODE_FONT__", _BRAND["code_font"])
        .replace("__ACCENT_HOT__", _BRAND["accent_hot"])
        .replace("__ACCENT__", _BRAND["accent"])
        # Built from the sources actually present, so each renders distinctly. Falling
        # back to the preferred-name keys keeps a caller that passes nothing working.
        .replace(
            "__SRC_COLORS__",
            _script_json(color_for_sources(sources if sources else SOURCE_COLORS.keys())),
        )
        .replace("__DATA_SHIM__", data_shim)
        .replace("__D3_SCRIPT__", _d3_script())
    )


# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #
def make_handler(model, engine, flags, sz, title):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path in ("/", "/index.html"):
                    return self._send(
                        200,
                        render_page(title, sources=model.data_sources()),
                        "text/html; charset=utf-8",
                    )
                if path == "/api/stats":
                    return self._send(200, json.dumps(model.stats()))
                if path == "/api/graph":
                    return self._send(200, json.dumps(model.graph()))
                if path == "/api/merges":
                    return self._send(200, json.dumps(model.merges()))
                if path == "/api/overlap":
                    return self._send(200, json.dumps(model.overlap()))
                if path == "/api/records":
                    eid = parse_qs(parsed.query).get("entity_id", [""])[0]
                    return self._send(200, json.dumps(model.records(eid)))
                if path == "/api/matchkeys":
                    return self._send(200, json.dumps(model.match_keys()))
                if path == "/api/features":
                    return self._send(200, json.dumps(model.feature_scores()))
                if path == "/api/search":
                    q = parse_qs(parsed.query).get("q", [""])[0]
                    return self._send(200, json.dumps(model.search(engine, flags, q)))
                if path == "/api/why":
                    eid = parse_qs(parsed.query).get("entity_id", [""])[0]
                    return self._send(200, json.dumps(model.why(engine, sz, eid)))
                if path == "/api/how":
                    eid = parse_qs(parsed.query).get("entity_id", [""])[0]
                    return self._send(200, json.dumps(model.how(engine, sz, eid)))
                return self._send(404, json.dumps({"error": "not found"}))
            except Exception as exc:  # never 500-crash silently
                return self._send(500, json.dumps({"error": str(exc)}))

    return Handler


def build_model(settings, patterns):
    from senzing import SzEngineFlags
    from senzing_core import SzAbstractFactoryCore

    # Keep the factory alive for the caller's lifetime: if it is garbage
    # collected, it destroys the engine it created ("engine object has been
    # destroyed"), which would break later /api/search requests.
    factory = SzAbstractFactoryCore("bootcamp_viz", settings, verbose_logging=False)
    engine = factory.create_engine()
    flags = SzEngineFlags.SZ_ENTITY_DEFAULT_FLAGS
    model = Model().build(engine, flags, _iter_record_keys(patterns))
    # Pre-compute the (capped) feature-score distribution so the Feature Scores tab
    # works in the live app and the offline snapshot. Guarded so a why failure or a
    # single-record-only data set never blocks the model/snapshot build (INV-077).
    try:
        model.compute_feature_dist(engine, SzEngineFlags)
    except Exception as exc:  # non-fatal (INV-077): leave a breadcrumb, don't block
        sys.stderr.write(
            f"feature-score distribution unavailable (non-fatal): "
            f"{type(exc).__name__}: {exc}\n"
        )
    # Return the flags class too, so the why/how endpoints can use the
    # MCP-confirmed default flag groups (SZ_HOW_ENTITY_DEFAULT_FLAGS, etc.).
    return factory, model, engine, flags, SzEngineFlags


def _esc_html(s):
    """Escape a data-sourced string for HTML **text or an attribute value** (INV-106).

    Quotes are escaped as well as ``& < >``, so one helper is safe in both contexts. It
    previously escaped only the three, which is correct for a text node and unsafe inside
    ``attr="…"`` — a value containing a double quote closes the attribute early and the
    remainder parses as markup. Every call site was a text node, so nothing was broken;
    the hazard was that INV-106 and the guidance in
    ``module-05-data-quality-mapping/phase1-quality-assessment.md`` both name the attribute
    context, so the next caller could reasonably have reached for this and been wrong. A
    footgun with no live victim is still a footgun (found by the 2026-07-30 sweep).

    Escaping quotes costs nothing in a text node: ``&quot;`` and ``&#39;`` render as
    ``"`` and ``'``. For a value going inside an inline ``<script>`` block use
    ``_script_json`` instead — HTML escaping is the wrong tool there.
    """
    return (
        str("" if s is None else s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _script_json(obj):
    """json.dumps safe to embed inside an inline <script> block. json.dumps does
    not escape "<", so a data-sourced string containing "</script>" would close
    the element early and let the remainder parse as HTML (a stored-XSS vector in
    the self-contained snapshot). Escaping "<"/">"/"&" as \\uXXXX keeps the JSON
    valid and byte-identical once parsed, but inert to the HTML parser."""
    return (
        json.dumps(obj)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _match_key_chips(match_key):
    """Split a Senzing match key (e.g. '+NAME+ADDRESS-DOB') into <span> chips,
    mirroring the live app's doSearch() rendering."""
    mk = match_key or ""
    parts, cur = [], ""
    for ch in mk:
        if ch in "+-":
            if cur:
                parts.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return "".join("<span>" + _esc_html(p) + "</span>" for p in parts if p)


def _result_card(searched, res):
    """Render one pre-rendered example search-result card (mirrors doSearch())."""
    rc = res.get("record_count")
    html = ['<div class="card">']
    html.append(
        '<div class="muted" style="margin-bottom:4px">Searched: <b>'
        + _esc_html(searched)
        + "</b></div>"
    )
    html.append("<h4>" + _esc_html(res.get("entity_name", "?")) + "</h4>")
    html.append(
        '<div class="muted">Entity '
        + _esc_html(res.get("entity_id"))
        + " · "
        + _esc_html(rc if rc is not None else "?")
        + " record(s) · "
        + _esc_html(", ".join(res.get("data_sources") or []))
        + "</div>"
    )
    if res.get("match_key"):
        html.append('<div class="mk">' + _match_key_chips(res["match_key"]) + "</div>")
    if res.get("resolution_rule"):
        html.append("<div><code>" + _esc_html(res["resolution_rule"]) + "</code></div>")
    html.append("</div>")
    return "".join(html)


def _snapshot_probe_html(model, engine, flags, port=8080, dataset=""):
    """Build the static snapshot's Search/Probe tab: a note plus a fixed set of
    pre-rendered example search results (no live search box, which cannot work in a
    static file). Examples are drawn from this snapshot's own multi-record entities
    and enriched via a real search so the match keys are truthful; if a search
    cannot run, the card falls back to the merge data (no match key)."""
    merges = model.merges().get("entities", [])
    # Prefer cross-source merges (the most interesting), then the rest, by size.
    ordered = sorted(
        merges,
        key=lambda e: (len(e.get("data_sources", [])) < 2, -e.get("record_count", 0)),
    )
    cards = []
    for ent in ordered:
        if len(cards) >= 5:
            break
        name = ent.get("entity_name") or ""
        if not name:
            continue
        res = None
        searchable = True
        try:
            hits = model.search(engine, flags, name).get("results", [])
            res = next(
                (h for h in hits if h.get("entity_id") == ent.get("entity_id")),
                hits[0] if hits else None,
            )
            if res is None:
                # The search ran and matched nothing, so this example is not
                # "pre-verified" and must not be offered as one — a hint that
                # returns nothing is worse than no hint. Distinct from the
                # exception case below, where search is simply unavailable.
                searchable = False
                sys.stderr.write(
                    f"dropped snapshot example {name!r}: search returned no match "
                    "(the example is not verified, so it is not offered)\n"
                )
        except Exception as exc:  # non-fatal (INV-077): fall back to merge data
            sys.stderr.write(
                f"snapshot probe search failed for {name!r} (non-fatal): "
                f"{type(exc).__name__}: {exc}\n"
            )
            res = None
        if not searchable:
            continue
        if res is None:  # search unavailable — render from the merge data itself
            res = {
                "entity_id": ent.get("entity_id"),
                "entity_name": name,
                "record_count": ent.get("record_count"),
                "data_sources": ent.get("data_sources", []),
                "match_key": "",
                "resolution_rule": "",
            }
        cards.append(_result_card(name, res))
    # The port comes from the parsed --port and the dataset wording from the caller: this
    # text ships into docs/visualizations/*.html, which is the retained keepsake. Hardcoding
    # them told a Module 7 bootcamper to open a port nothing was listening on and called
    # their own data "this Truth Set" — the app serves the Truth Set in one module and the
    # bootcamper's data in another, from this one code path.
    where = _esc_html(dataset.strip()) if dataset and dataset.strip() else "the loaded data"
    note = (
        '<p class="muted">This is a saved snapshot, so live search is disabled. Below are '
        f"example searches run against {where}. In the live app "
        f"(<code>http://localhost:{int(port)}</code>) you can search any name.</p>"
    )
    # #probe-btns must exist here too, or `loadProbes()` has nothing to render into and the
    # snapshot silently loses the "Show all merged entities" browse — the one capability the
    # removed Record Merges tab uniquely had, and one that previously worked offline. It needs
    # no engine: it reads the embedded `merges` payload, so it works with no server.
    browse = '<div id="probe-btns"></div>'
    if not cards:
        return note + browse + '<p class="muted">No multi-record entities to show.</p>'
    return note + browse + '<div id="results">' + "".join(cards) + "</div>"


def write_snapshot(model, engine, flags, title, out_path, port=8080, dataset=""):
    """Write a fully self-contained HTML snapshot with D3 and data embedded, so it
    renders with no server and no network access."""
    payload = {
        "stats": model.stats(),
        "graph": model.graph(),
        "merges": model.merges(),
        # No "records" key: /api/records is per-entity, and graph.nodes already
        # carries every entity with its constituent records, so the shim below
        # indexes those instead. A second full copy would have embedded the same
        # records twice in a file whose size grows with the bootcamper's dataset.
        "overlap": model.overlap(),
        "matchkeys": model.match_keys(),
        "features": model.feature_scores(),
    }
    # The embedded-data shim runs after D3 and before the page bootstrap, replacing
    # the fetch-based bootstrap with the inlined data.
    #
    # ⛔ /api/records is the one endpoint whose response depends on the query string.
    # Returning the whole collection for it — as the aggregate endpoints below
    # correctly do — hands showRecords() an object with no `records` array, so every
    # entity in a standalone snapshot reported "No records returned for this entity"
    # while the live server showed them. Resolve the entity_id here instead.
    shim = (
        "<script>const __DATA__=" + _script_json(payload) + ";"
        "var __RECS__=null;"
        "function __recordsFor(id){if(!__RECS__){__RECS__={};"
        "(((__DATA__.graph||{}).nodes)||[]).forEach(function(n){"
        "__RECS__[String(n.entity_id)]={entity_id:n.entity_id,entity_name:n.entity_name,"
        "records:n.records||[]};});}"
        "return __RECS__[id]||{entity_id:id,error:'not found: no such entity'};}"
        "window.fetch=function(u){var p=u.split('?')[0].replace('/api/','');"
        "var q=(u.split('?')[1]||'');"
        "if(p==='search'){return Promise.resolve({json:function(){return Promise.resolve({results:[]});}});}"
        "if(p==='why'||p==='how'){return Promise.resolve({json:function(){return Promise.resolve({error:'Why/How explanations run only against the live visualization server (start it with: python3 senzing_viz_server.py --records ...).'});}});}"
        "if(p==='records'){var m=q.match(/entity_id=([^&]*)/);"
        "var r=__recordsFor(m?decodeURIComponent(m[1]):'');"
        "return Promise.resolve({json:function(){return Promise.resolve(r);}});}"
        "return Promise.resolve({json:function(){return Promise.resolve(__DATA__[p]);}});};</script>"
    )
    page = render_page(
        title,
        data_shim=shim,
        probe_body=_snapshot_probe_html(model, engine, flags, port=port, dataset=dataset),
        sources=model.data_sources(),
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)


#: The `PIPELINE` keys the engine needs before it can initialize. A settings document
#: missing any of them is incomplete, however valid its JSON.
REQUIRED_PIPELINE_KEYS = ("CONFIGPATH", "RESOURCEPATH", "SUPPORTPATH")


def _pipeline_gaps(raw):
    """Missing REQUIRED_PIPELINE_KEYS for `raw`, or None when `raw` is not usable JSON.

    None and [] are deliberately different: None means "cannot tell" (unparseable, or not
    an object), [] means "parsed and complete".
    """
    if not raw or not raw.strip():
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(doc, dict):
        return None
    pipeline = doc.get("PIPELINE")
    if not isinstance(pipeline, dict):
        return list(REQUIRED_PIPELINE_KEYS)
    return [k for k in REQUIRED_PIPELINE_KEYS if not str(pipeline.get(k, "")).strip()]


def resolve_settings(path, env_value, log):
    """(settings, source, problem) — pick the settings document, content-aware.

    Returns `problem` as a ready-to-write message when neither source is usable; otherwise
    `problem` is None and `source` describes what won, for the caller to report.

    ⛔ Precedence is content-aware on purpose (INV-210). The previous implementation was
    `if os.path.exists(path)` — existence-based — so a `{"PIPELINE": {}}` stub silently beat
    a fully populated env var, and the run then failed deep in the engine with `SENZ7426`,
    an error whose documented meaning ("check SUPPORTPATH first; this is a configuration
    error, not a broken install") points at the wrong thing entirely. The losing source is
    never discarded silently: whenever both are present, which one is in force is stated.
    """
    file_raw = ""
    file_unreadable = False
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                file_raw = fh.read()
        except OSError as exc:
            file_unreadable = True
            log.write(f"settings: cannot read {path} ({exc}); falling back to "
                      f"$SENZING_ENGINE_CONFIGURATION_JSON\n")

    file_gaps = _pipeline_gaps(file_raw)
    env_gaps = _pipeline_gaps(env_value)
    file_ok = file_gaps == []
    env_ok = env_gaps == []
    both_present = bool(file_raw.strip() or file_unreadable) and bool(env_value.strip())

    if file_ok:
        if both_present and env_ok and file_raw.strip() != env_value.strip():
            log.write(f"settings: using {path}; $SENZING_ENGINE_CONFIGURATION_JSON is also "
                      "set and differs — the file wins.\n")
        return file_raw, path, None

    if env_ok:
        if file_raw.strip() or file_unreadable:
            why = "unreadable" if file_unreadable else (
                "missing PIPELINE " + ", ".join(file_gaps) if file_gaps
                else "not usable JSON")
            log.write(f"settings: {path} is {why}; using "
                      "$SENZING_ENGINE_CONFIGURATION_JSON instead.\n")
        return env_value, "$SENZING_ENGINE_CONFIGURATION_JSON", None

    # Neither is usable. Name the source that was tried and exactly what it lacks, so the
    # reported cause is the real one rather than whatever the engine says three calls later.
    if file_gaps:
        return "", path, (
            f"Engine settings in {path} are incomplete: PIPELINE is missing "
            f"{', '.join(file_gaps)}.\n"
            "The engine cannot initialize without them, and proceeding would fail with "
            "SENZ7426 (transliteration), which points at SUPPORTPATH rather than at this "
            "file. Fix the file, or unset it and export a complete "
            "$SENZING_ENGINE_CONFIGURATION_JSON.\n")
    if env_gaps:
        return "", "$SENZING_ENGINE_CONFIGURATION_JSON", (
            "Engine settings in $SENZING_ENGINE_CONFIGURATION_JSON are incomplete: "
            f"PIPELINE is missing {', '.join(env_gaps)}.\n")
    if file_raw.strip() and file_gaps is None:
        return "", path, (
            f"Engine settings in {path} are not usable JSON (expected an object with a "
            "PIPELINE section).\n")
    if env_value.strip() and env_gaps is None:
        return "", "$SENZING_ENGINE_CONFIGURATION_JSON", (
            "Engine settings in $SENZING_ENGINE_CONFIGURATION_JSON are not usable JSON "
            "(expected an object with a PIPELINE section).\n")
    return "", None, "No engine settings (missing --settings file and env var).\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--settings", default="config/engine_config.json")
    ap.add_argument("--records", nargs="+", required=True,
                    help="JSONL file(s)/glob(s) of the records that were loaded")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--title", default="Senzing Entity Resolution")
    ap.add_argument("--dataset", default="",
                    help="what the loaded data IS, for snapshot wording (e.g. 'the Senzing "
                         "Truth Set', 'your CUSTOMERS and REFERENCE data'). Left empty the "
                         "snapshot says 'the loaded data' — never assume the Truth Set.")
    ap.add_argument("--snapshot", default=None,
                    help="also write a self-contained standalone HTML to this path")
    ap.add_argument("--no-serve", action="store_true",
                    help="build the model (and snapshot) then exit without serving")
    args = ap.parse_args(argv)

    settings, source, problem = resolve_settings(args.settings,
                                                 os.getenv("SENZING_ENGINE_CONFIGURATION_JSON", ""),
                                                 sys.stderr)
    if problem:
        sys.stderr.write(problem)
        return 2
    _ = source

    try:
        factory, model, engine, flags, sz = build_model(settings, args.records)
    except Exception as exc:
        sys.stderr.write(f"Could not build entity model: {type(exc).__name__}: {exc}\n")
        return 1
    # `factory` must stay referenced for the whole run so the engine survives.
    _ = factory

    s = model.stats()
    print(f"Entity model built: {s['records_total']} records, {s['entities_total']} entities, "
          f"{s['multi_record_entities']} merged, {s['cross_source_entities']} cross-source, "
          f"{s['relationships_total']} relationships")

    if args.snapshot:
        write_snapshot(model, engine, flags, args.title, args.snapshot,
                       port=args.port, dataset=args.dataset)
        print(f"Snapshot written: {args.snapshot}")

    if args.no_serve:
        return 0

    handler = make_handler(model, engine, flags, sz, args.title)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Visualization running: http://localhost:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
