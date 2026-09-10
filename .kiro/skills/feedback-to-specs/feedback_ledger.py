#!/usr/bin/env python3
"""Per-entry duplicate detection and archiving for bootcamp feedback files.

MAINTAINER TOOL. This file lives under `.kiro/skills/` and is never ported into the
Bootcamp_Power: it is part of developing the Power, not part of running the bootcamp.

Feedback files arrive from **multiple bootcampers at multiple times**, so the realistic
collision is not "the identical file twice" — it is a file that *overlaps* a previous
one. A bootcamper's project accumulates entries during a run; a later copy dropped into
this repository holds the earlier entries **plus** new ones. Comparing whole files gets
that wrong in both directions: a byte-compare calls it new and every entry is re-specced,
and a whole-file duplicate verdict would discard the genuinely new entries.

So identity here is **per entry**, and it is content-addressed:

* an entry is one ``## <title>`` block (heading through the line before the next ``##``
  heading, or EOF), scaffold headings excluded;
* its id is ``sha256`` of the entry's **normalized** text, first 16 hex chars.

Normalization matters as much as the hash. A file re-saved on Windows can gain a UTF-8
BOM or CRLF line endings without any content change, and PowerShell can double-encode it
outright — all of which change bytes. Normalizing first is what stops "same feedback,
different bytes" from reading as new work. The rules are fixed here, in code, rather than
described in prose, because a later run that normalized even slightly differently would
produce different ids and silently re-process everything.

ONE FILENAME. ``SENZING_BOOTCAMP_POWER_FEEDBACK.md`` is the Kiro Power's feedback file.
``SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md`` is **reserved for the Senzing Bootcamp Claude
plugin** and is deliberately not accepted here: the two artifacts are developed in separate
repositories, and a helper that silently took either name would let a Claude plugin's
feedback be triaged into Kiro specs — routed to homes (`contract`, `kiro-owned`, `engine`)
that do not exist on that side. Refusing the reserved name is what keeps the two streams
from crossing.

The ledger is ``docs/feedback/PROCESSED.jsonl`` — one JSON object per processed entry,
append-only and read **last-wins**, so a disposition can be corrected by appending a
superseding line (``annotate``) without ever rewriting history. It answers "has this been
processed?" in one read, and also answers the question nothing else can: **which spec came
from this entry?**

Usage::

    feedback_ledger.py find [--repo <dir>]
    feedback_ledger.py check <candidate.md> [--repo <dir>]
    feedback_ledger.py commit <candidate.md> [--repo <dir>] [--disposition title=spec ...]
    feedback_ledger.py annotate <entry_id> "<disposition>" [--repo <dir>]

``find`` lists candidate files, archive and rejected duplicates excluded. ``check``
classifies every entry and exits 0 (some entries are new), 3 (every entry has been
processed — a full duplicate) or 1 (bad input); it writes nothing. ``commit`` archives the
candidate under ``docs/feedback/`` and appends one ledger line per newly processed entry;
for a full duplicate it instead renames the candidate in place and appends nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

LEDGER_NAME = "PROCESSED.jsonl"

#: Where processed files come to rest. Under `docs/` because this repository already keeps
#: its maintainer-facing records there (`docs/test-records/`), and because a tree the
#: transformation engine never reads cannot be confused with Power content.
ARCHIVE_DIR = "docs/feedback"

#: The Kiro Power's feedback file. Exactly one name. See the module docstring.
CANDIDATE_NAME = "SENZING_BOOTCAMP_POWER_FEEDBACK.md"

#: The Claude plugin's feedback file. Recognized ONLY so a maintainer who drops it here is
#: told what it is, instead of getting "no feedback file found" and hunting for a typo.
RESERVED_NAME = "SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md"

#: Where a candidate is looked for, in resolution order. `docs/feedback/` is deliberately
#: absent: it is the archive, never a candidate.
CANDIDATE_DIRS = (".", "docs")

#: Marker on a file whose every entry was already processed. Such a file is renamed rather
#: than archived, and must never be offered as a candidate again.
DUPLICATE_MARKER = "_DUPLICATE"

# An entry starts at a `## ` heading. The feedback template uses `## Improvement: <title>`,
# but bootcampers do not always follow it, so any H2 that is not one of the file's own
# scaffold headings counts as an entry.
_ENTRY_HEADING = re.compile(r"(?m)^##\s+(?P<title>\S.*?)\s*$")

# Scaffold headings that are part of the file, not feedback: skipped so an empty
# "Your Feedback" placeholder never becomes a processed entry.
_SCAFFOLD_TITLES = {
    "your feedback",
    "feedback",
    "senzing bootcamp power feedback",
    "how to use this file",
    "template",
}


def normalize(text: str) -> str:
    """Content-only form of a document or entry, stable across trivial re-saves.

    Strips a UTF-8 BOM, normalizes CRLF/CR to LF, right-strips every line, collapses
    runs of blank lines to one, and strips leading/trailing blank lines. Deliberately
    does NOT touch case or interior spacing: a reworded entry is a different entry, and a
    maintainer should see a revised report.
    """
    text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for line in (raw.rstrip() for raw in text.split("\n")):
        if not line and out and not out[-1]:
            continue
        out.append(line)
    return "\n".join(out).strip("\n")


def entry_id(entry_text: str) -> str:
    """Content-addressed id for one entry: sha256 of its normalized text, 16 hex chars."""
    return hashlib.sha256(normalize(entry_text).encode("utf-8")).hexdigest()[:16]


def split_entries(text: str) -> list[tuple[str, str]]:
    """Split a feedback document into [(title, entry_text)], scaffold headings dropped."""
    normalized = normalize(text)
    matches = list(_ENTRY_HEADING.finditer(normalized))
    entries: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        title = match.group("title").strip()
        body = normalized[start:end].strip("\n")
        # A heading with no content under it is a placeholder, not an entry.
        content = body[len(match.group(0)) :].strip()
        if title.lower().rstrip(":") in _SCAFFOLD_TITLES or not content:
            continue
        entries.append((title, body))
    return entries


def archive_stem(candidate: Path) -> str:
    """The archive's filename stem: the candidate's own, so provenance survives.

    Keeping the arriving stem is what lets both accepted filenames coexist in one
    archive directory without either being relabelled as the other.
    """
    return candidate.name[: -len(".md")] if candidate.name.endswith(".md") else candidate.name


def find_candidates(repo: Path) -> list[Path]:
    """Unprocessed feedback files, in resolution order.

    Excludes the archive directory and anything already marked a duplicate, so a
    resolution step cannot re-offer a file that has been dealt with. That exclusion is
    code rather than prose because it is the one mistake with an irreversible cost: a
    second archive of an already-archived file.
    """
    archive = (repo / ARCHIVE_DIR).resolve()
    found: list[Path] = []
    for directory in CANDIDATE_DIRS:
        base = (repo / directory).resolve()
        if not base.is_dir() or base == archive:
            continue
        path = base / CANDIDATE_NAME
        if path.is_file() and DUPLICATE_MARKER not in path.name:
            found.append(path)
    return found


def find_reserved(repo: Path) -> list[Path]:
    """Claude-plugin feedback files sitting where a Kiro one was expected.

    Reported, never processed. A maintainer who copies the wrong artifact's feedback in
    has made a specific mistake with a specific remedy — take it to the Claude plugin
    repository — and "no feedback file found" does not say that.
    """
    archive = (repo / ARCHIVE_DIR).resolve()
    found: list[Path] = []
    for directory in CANDIDATE_DIRS:
        base = (repo / directory).resolve()
        if not base.is_dir() or base == archive:
            continue
        path = base / RESERVED_NAME
        if path.is_file():
            found.append(path)
    return found


def read_ledger(repo: Path) -> dict[str, dict]:
    """{entry_id: record} from the ledger, last line winning; {} when absent.

    Last-wins is what makes `annotate` a correction rather than a rewrite: the file is
    append-only, so the current answer is the latest line for an id.
    """
    path = repo / ARCHIVE_DIR / LEDGER_NAME
    seen: dict[str, dict] = {}
    if not path.is_file():
        return seen
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue  # a malformed line must not hide the rest of the ledger
            if record.get("entry_id"):
                seen[record["entry_id"]] = record
    return seen


def classify(candidate: Path, repo: Path) -> dict:
    """Every entry in `candidate`, split into new and already-processed."""
    text = candidate.read_text(encoding="utf-8", errors="replace")
    entries = split_entries(text)
    seen = read_ledger(repo)
    new: list[dict] = []
    known: list[dict] = []
    for title, body in entries:
        identifier = entry_id(body)
        record = {"entry_id": identifier, "title": title, "record": seen.get(identifier)}
        (known if identifier in seen else new).append(record)
    return {
        "candidate": str(candidate),
        "file_id": entry_id(text),
        "entries_total": len(entries),
        "new": new,
        "known": known,
    }


def _archive_unixtime_of(known: list[dict]) -> str:
    """The archive timestamp a fully-duplicate candidate duplicates."""
    stamps = [
        str((item.get("record") or {}).get("archive_unixtime"))
        for item in known
        if (item.get("record") or {}).get("archive_unixtime")
    ]
    if not stamps:
        return str(int(time.time()))
    # Every entry should trace to one archive; if several, name the earliest.
    return sorted(stamps)[0]


def _unique(path: Path) -> Path:
    """`path`, or the first `-2`, `-3`, … variant that does not exist."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find an unused name beside {path}")


def cmd_find(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    candidates = find_candidates(repo)
    if not candidates:
        for reserved in find_reserved(repo):
            sys.stderr.write(
                f"Found {reserved} — that name is reserved for the Senzing Bootcamp "
                "Claude plugin and is not processed here. The Kiro Power's feedback file "
                f"is {CANDIDATE_NAME}; take a plugin feedback file to the plugin's own "
                "development repository.\n"
            )
        sys.stderr.write(
            f"No unprocessed feedback file found. Looked for {CANDIDATE_NAME} under "
            f"{', '.join(CANDIDATE_DIRS)}/ (the {ARCHIVE_DIR}/ archive is never a "
            "candidate).\n"
        )
        return 1
    for path in candidates:
        print(path.relative_to(repo) if path.is_relative_to(repo) else path)
    if len(candidates) > 1:
        sys.stderr.write(
            f"\n{len(candidates)} candidates found — ask the maintainer which to process.\n"
        )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    candidate = Path(args.candidate)
    if not candidate.is_file():
        sys.stderr.write(f"No such feedback file: {candidate}\n")
        return 1
    if candidate.name == RESERVED_NAME:
        sys.stderr.write(
            f"{candidate} carries the name reserved for the Senzing Bootcamp Claude "
            f"plugin. This repository develops the Kiro Power; its feedback file is "
            f"{CANDIDATE_NAME}. Refusing to process it.\n"
        )
        return 1
    if DUPLICATE_MARKER in candidate.name:
        sys.stderr.write(
            f"{candidate} is a rejected duplicate, not a candidate. Nothing to process.\n"
        )
        return 1
    if (repo / ARCHIVE_DIR).resolve() in candidate.resolve().parents:
        sys.stderr.write(
            f"{candidate} is already archived under {ARCHIVE_DIR}/. The archive is a "
            "record, never an input — ask the maintainer which file they meant.\n"
        )
        return 1
    result = classify(candidate, repo)
    if result["entries_total"] == 0:
        sys.stderr.write(
            f"{candidate}: no feedback entries found (only scaffold/placeholder "
            "headings). Nothing to process.\n"
        )
        return 1
    print(json.dumps(result, indent=2))
    if not result["new"]:
        sys.stderr.write(
            f"\nVERDICT: DUPLICATE — all {result['entries_total']} entries are already in "
            f"{ARCHIVE_DIR}/{LEDGER_NAME}. Duplicates the archive at unixtime "
            f"{_archive_unixtime_of(result['known'])}.\n"
        )
        return 3
    if result["known"]:
        sys.stderr.write(
            f"\nVERDICT: PARTIAL — {len(result['new'])} new entr(y/ies), "
            f"{len(result['known'])} already processed. Triage ONLY the new ones.\n"
        )
    else:
        sys.stderr.write(
            f"\nVERDICT: NEW — all {result['entries_total']} entries are unprocessed.\n"
        )
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    candidate = Path(args.candidate)
    if not candidate.is_file():
        sys.stderr.write(f"No such feedback file: {candidate}\n")
        return 1
    if candidate.name == RESERVED_NAME:
        sys.stderr.write(
            f"{candidate} carries the name reserved for the Senzing Bootcamp Claude "
            f"plugin. This repository develops the Kiro Power; its feedback file is "
            f"{CANDIDATE_NAME}. Refusing to archive it.\n"
        )
        return 1
    result = classify(candidate, repo)
    if result["entries_total"] == 0:
        sys.stderr.write(f"{candidate}: no entries; refusing to archive.\n")
        return 1

    archive_dir = repo / ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    stem = archive_stem(candidate)

    # Full duplicate: rename in place, name the archive it duplicates, append nothing.
    if not result["new"]:
        stamp = _archive_unixtime_of(result["known"])
        target = _unique(candidate.with_name(f"{stem}_{stamp}{DUPLICATE_MARKER}.md"))
        candidate.rename(target)
        print(f"DUPLICATE: {candidate} -> {target} (nothing processed, ledger unchanged)")
        return 3

    stamp = str(int(time.time()))
    target = _unique(archive_dir / f"{stem}_{stamp}.md")

    # rpartition, not partition: an entry title legitimately contains "=" — e.g.
    # "sdk_guide(topic='configure') snippet fails …" — and splitting on the FIRST "="
    # truncates the key and silently drops the disposition. A spec path never contains
    # "=", so the last one is the separator. An entry_id is accepted as the key too, for
    # a title that is awkward to quote on a command line.
    dispositions: dict[str, str] = {}
    for pair in args.disposition or []:
        key, separator, value = pair.rpartition("=")
        if not separator:
            sys.stderr.write(f"ignoring --disposition without '=': {pair!r}\n")
            continue
        if key.strip():
            dispositions[key.strip()] = value.strip()

    processed_on = time.strftime("%Y-%m-%d", time.gmtime())
    lines = [
        json.dumps(
            {
                "entry_id": item["entry_id"],
                "title": item["title"],
                "archive": target.name,
                "archive_unixtime": stamp,
                "processed": processed_on,
                "disposition": dispositions.get(
                    item["title"], dispositions.get(item["entry_id"], "unrecorded")
                ),
            },
            sort_keys=True,
        )
        for item in result["new"]
    ]
    ledger = archive_dir / LEDGER_NAME
    with ledger.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")

    candidate.rename(target)
    print(f"ARCHIVED: {candidate} -> {target}")
    print(f"LEDGER:   +{len(lines)} entr(y/ies) in {ledger}")
    if result["known"]:
        print(
            f"NOTE:     {len(result['known'])} entr(y/ies) in this file were already "
            "processed and were not re-recorded."
        )
    unrecorded = sum(1 for line in lines if '"disposition": "unrecorded"' in line)
    if unrecorded:
        sys.stderr.write(
            f'WARNING:  {unrecorded} entr(y/ies) recorded with disposition "unrecorded" '
            '— pass --disposition "<title>=<spec-or-outcome>" so the ledger says which '
            "spec each entry produced.\n"
        )
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    """Append a superseding record for one entry, to set or correct its disposition.

    The ledger is append-only and read last-wins, so a correction is a new line rather
    than an edit: history stays intact and the current answer is the latest line for that
    ``entry_id``.
    """
    repo = Path(args.repo).resolve()
    record = read_ledger(repo).get(args.entry_id)
    if record is None:
        sys.stderr.write(
            f"No ledger record for entry_id {args.entry_id!r}. Run `check` on the source "
            "file to list ids.\n"
        )
        return 1
    updated = dict(record)
    updated["disposition"] = args.disposition
    updated["annotated"] = time.strftime("%Y-%m-%d", time.gmtime())
    ledger = repo / ARCHIVE_DIR / LEDGER_NAME
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(updated, sort_keys=True) + "\n")
    print(
        f"ANNOTATED: {args.entry_id} disposition -> {args.disposition!r} "
        "(appended; the ledger reads last-wins)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    find = sub.add_parser("find", help="list unprocessed candidates; writes nothing")
    find.set_defaults(func=cmd_find)

    check = sub.add_parser("check", help="classify a candidate's entries; writes nothing")
    check.add_argument("candidate")
    check.set_defaults(func=cmd_check)

    commit = sub.add_parser("commit", help="archive the candidate and record its entries")
    commit.add_argument("candidate")
    commit.add_argument(
        "--disposition",
        action="append",
        metavar="TITLE=SPEC",
        help='what an entry produced, e.g. "Screenshot capture fails='
        '.kiro/specs/screenshot-capture-fails/" or "Vague thing=needs-clarification". '
        "Repeatable.",
    )
    commit.set_defaults(func=cmd_commit)

    annotate = sub.add_parser(
        "annotate", help="append a superseding line to set/correct one entry's disposition"
    )
    annotate.add_argument("entry_id")
    annotate.add_argument("disposition")
    annotate.set_defaults(func=cmd_annotate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
