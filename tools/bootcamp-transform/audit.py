#!/usr/bin/env python3
"""Lead generators for the production-readiness audit. Read-only; exits 0.

    audit.py rules       [--uncited]      hard rules, with the invariants cited AT each one
    audit.py since       [--ref <ref>]    hard-rule lines added since a ref (default: newest tag)
    audit.py citations   [--parent-invariants <file> | --offline]
                                          every INV-/KINV- citation resolves to a definition
    audit.py references                   skill names and slash commands nothing ships
    audit.py enumerations [--parent-invariants <file>]
                                          invariants that enumerate, i.e. go stale
    audit.py duplication [--words N] [--top N]
    audit.py size
    audit.py all         [--offline]      every view that needs no range

The canonical family operation `production-readiness-audit` (FAMILY_WORKFLOW R4), ported
from the parent's `conformance.py`. The audit, not the parent's file layout: the views
read `powers/senzing-bootcamp/`, the Power a bootcamper installs, and every view splits
what it finds by the build's own record of where each file comes from
(`.build-manifest.json` `owner`), because the two halves route differently (R6):

* **kiro-owned** — authored in this repository. A hard rule here that cites nothing is a
  candidate for the `KINV-NNN` ledger, or a missing citation to an entry in it. Local.
* **template** — ported from the parent. A hard rule here is the parent's to register,
  in its own `INV-NNN` namespace; a finding about it is parent-bound and goes through
  `escalate-to-parent`.

⛔ **Every view is a lead generator, not a verdict.** A regex cannot tell a deliberately
restated rule from one that drifted, nor a worked illustration from a cached authority.
Read every hit before classifying it. A run that reports these counts as findings has
not done the audit; it has run a grep.

Each view states what it could not check as well as what it checked (INV-308): a
citation whose registry was unavailable is counted as *unverified*, never as resolved.
"""

from __future__ import annotations

import sys

# Read-only means not even bytecode: switched off before any sibling import.
sys.dont_write_bytecode = True

import argparse  # noqa: E402
import collections  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Iterable, Sequence  # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parent
#: tools/bootcamp-transform/audit.py -> repository root
DEFAULT_REPO = ENGINE_ROOT.parent.parent

POWER_REL = "powers/senzing-bootcamp"
MANIFEST_NAME = ".build-manifest.json"
LEDGER_REL = "specs/INVARIANTS.md"
PARENT_DEVELOPMENT_REPOSITORY = "docktermj/senzing-bootcamp-claude-plugin-development"
PARENT_INVARIANTS_PATH = "specs/INVARIANTS.md"

#: ⛔ The roots `since` diffs, defined once (INV-308: one definition every consumer reads).
#: The shipped Power, the authored source of its kiro-owned half, and the maintainer
#: surface whose rules this repository owns outright.
SINCE_ROOTS = (
    POWER_REL,
    "tools/bootcamp-transform/templates/kiro-owned",
    "powers/senzing-bootcamp-maintainer",
)

OWNER_KIRO = "kiro"
OWNER_TEMPLATE = "template"
#: Files the build generates and the manifest does not record as ported or authored.
UNRECORDED = "unrecorded"

INV_ID = re.compile(r"\bINV-\d{3}\b")
KINV_ID = re.compile(r"\bKINV-\d{3}\b")
ANY_ID = re.compile(r"\b(?:K?INV)-\d{3}\b")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# The house convention for a deliberate hard rule, shared with the parent: a ⛔ lead-in or
# a bolded MUST/NEVER/ALWAYS. Bare prose "must" is ordinary instruction and is excluded —
# in the parent, including it took the candidate list from 16 to 202, which no one reads.
ANCHORED_RULE = re.compile(
    r"^\s*>?\s*⛔"
    r"|\*\*[^*]*\b(?:MUST|NEVER|ALWAYS)\b[^*]*\*\*"
    r"|^\s*-?\s*\*\*.*?\*\*.*\b(?:MUST|NEVER)\b"
)
CODE_SPAN = re.compile(r"`[^`]*`")
IMPERATIVE = (r"never|always|do not|don't|use|keep|prefer|treat|stop|ask|read|write|check"
              r"|state|name|strip|report|verify|cite|record|leave|derive|scope")
MID_LINE_RULE = re.compile(r"⛔\s*(?:\*\*|[A-Z]|(?:%s)\b)" % IMPERATIVE, re.IGNORECASE)
#: The stop sign used as a noun is prose about the convention, not a rule.
NOUN_USE = re.compile(
    r"(?:\b(?:a|an|the|its|any|each|every|marked|old|same)\s+(?:\w+\s+)?)⛔"
    r"|⛔\s*(?:gates?|convention|marker|lead-in|sign|glyphs?)\b",
    re.IGNORECASE,
)


def classify(line: str) -> str | None:
    """`anchored`, `mid-line`, or None — the single definition every view uses."""
    if ANCHORED_RULE.search(line):
        return "anchored"
    if "⛔" not in line:
        return None
    bare = CODE_SPAN.sub("", line)
    if "⛔" not in bare or bare.rstrip().endswith("⛔"):
        return None
    if NOUN_USE.search(bare):
        return None
    return "mid-line" if MID_LINE_RULE.search(bare) else None


# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------


class Corpus:
    """The shipped Power's markdown, each file tagged with the owner the build recorded."""

    def __init__(self, repo: Path):
        self.repo = repo
        self.power = repo / POWER_REL
        manifest_path = self.power / MANIFEST_NAME
        if not manifest_path.is_file():
            raise SystemExit(f"no {POWER_REL}/{MANIFEST_NAME} under {repo} — wrong --repo?")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.template_release = str(manifest.get("templateRelease", ""))
        self.owners = {e["path"]: e.get("owner", OWNER_TEMPLATE) for e in manifest.get("files", [])}
        self.sources = {e["path"]: e.get("sourcePath") for e in manifest.get("files", [])}
        # The Publication_Contract's own exclude list: the Power's maintainer CHANGELOG.md
        # is built here and never reaches a bootcamper, so it is not audited as shipped text.
        import propagate  # deferred: dont_write_bytecode is already set

        self.unpublished = {
            str(rule["path"]) for rule in propagate.load_contract(propagate.DEFAULT_CONTRACT).get("exclude") or []
        }

    def markdown(self) -> list[Path]:
        """Shipped markdown: what a bootcamper installs, so not what publication excludes."""
        return sorted(
            p for p in self.power.rglob("*.md")
            if p.is_file() and self.rel(p) not in self.unpublished
        )

    def rel(self, path: Path) -> str:
        return path.relative_to(self.power).as_posix()

    def owner(self, path: Path) -> str:
        return self.owners.get(self.rel(path), UNRECORDED)

    def lines(self, path: Path) -> list[str]:
        return path.read_text(encoding="utf-8").splitlines()

    def skill_names(self) -> set[str]:
        root = self.power / "skills"
        return {p.name for p in root.iterdir() if (p / "SKILL.md").is_file()} if root.is_dir() else set()


def own_citations(lines: Sequence[str], i: int) -> list[str]:
    """Invariant ids cited by the rule itself or the one non-blank line either side.

    Deliberately narrower than a section: the question is whether a reader **at this
    line** can name the governing rule (INV-183), and a citation thirty lines up under
    the same heading answers a different question.
    """
    window = [lines[i]]
    for step in (-1, 1):
        j = i + step
        while 0 <= j < len(lines) and not lines[j].strip():
            j += step
        if 0 <= j < len(lines):
            window.append(lines[j])
    return sorted(set(ANY_ID.findall("\n".join(window))))


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def cmd_rules(corpus: Corpus, args) -> int:
    """Every hard rule with the invariants cited at it, split by owner."""
    print("== hard rules in the shipped Power, with the invariants cited AT each one\n")
    totals = collections.Counter()
    bare = collections.Counter()
    for owner in (OWNER_KIRO, OWNER_TEMPLATE, UNRECORDED):
        printed_header = False
        for path in corpus.markdown():
            if corpus.owner(path) != owner:
                continue
            lines = corpus.lines(path)
            rows = []
            for i, line in enumerate(lines):
                if classify(line) is None:
                    continue
                totals[owner] += 1
                cited = own_citations(lines, i)
                if owner == OWNER_KIRO:
                    # A kiro-owned rule is answerable to the KINV ledger first.
                    governing = [c for c in cited if c.startswith("KINV-")] or cited
                else:
                    governing = cited
                if not governing:
                    bare[owner] += 1
                elif args.uncited:
                    continue
                rows.append((i + 1, governing, line.strip()))
            if not rows:
                continue
            if not printed_header:
                print(f"   [{owner}]")
                printed_header = True
            print(f"   {POWER_REL}/{corpus.rel(path)}")
            for lineno, governing, text in rows:
                cites = ",".join(governing) if governing else "(no citation at the rule)"
                print(f"     :{lineno:<5d} {cites:<24} {text[:84]}")
    print()
    for owner in (OWNER_KIRO, OWNER_TEMPLATE, UNRECORDED):
        if totals[owner]:
            print(f"   {owner:<10} {totals[owner]:4d} hard-rule lines, {bare[owner]:4d} citing nothing at the rule")
    print()
    print("   ^ a worklist to READ, not a count of unregistered rules.")
    print("     kiro-owned, uncited  -> a Kiro-native rule: cite its KINV, or draft one for")
    print("                             specs/INVARIANTS.md with the maintainer's sign-off. Local.")
    print("     template, uncited    -> the parent's rule to register in its INV namespace.")
    print("                             Parent-bound: escalate-to-parent, never a KINV here.")
    print("   ⚠ A hard rule written with no ⛔ and no bolded MUST/NEVER/ALWAYS is invisible here;")
    print("     this is a floor on what the reverse contract can see mechanically.")
    return 0


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def newest_tag(repo: Path) -> str | None:
    tags = [t for t in _git(repo, "tag", "--list").split() if SEMVER.match(t)]
    return max(tags, key=lambda t: tuple(int(p) for p in t.split("."))) if tags else None


def cmd_since(corpus: Corpus, args) -> int:
    """Hard-rule lines added since a ref, with what each cites; verdict per INV-308."""
    repo = corpus.repo
    ref = args.ref or newest_tag(repo)
    how = "--ref" if args.ref else "the newest semver tag"
    if not ref:
        print("== since: no ref given and this repository has no semver tag — NOT checked")
        return 0
    diff = _git(repo, "diff", "--unified=1", "--no-color", "-M", ref, "--", *SINCE_ROOTS)
    print(f"== hard-rule lines added since {ref} ({how}), across: {', '.join(SINCE_ROOTS)}\n")
    added = cited = 0
    current = None
    window: list[str] = []
    rows = collections.OrderedDict()
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            current = raw[6:] if raw.startswith("+++ b/") else None
            window = []
            continue
        if raw.startswith(("--- ", "diff ", "index ", "@@")):
            window = []
            continue
        body = raw[1:] if raw[:1] in "+- " else raw
        if raw.startswith("+") and current and current.endswith(".md") and classify(body):
            added += 1
            ids = sorted(set(ANY_ID.findall("\n".join(window[-1:] + [body]))))
            if ids:
                cited += 1
            rows.setdefault(current, []).append((ids, body.strip()))
        if not raw.startswith("-"):
            window.append(body)
    for name, items in rows.items():
        print(f"   {name}")
        for ids, text in items:
            print(f"     {(','.join(ids) or '(cites nothing)'):<24} {text[:84]}")
    print(f"\n   {added} hard-rule line(s) added, {cited} citing an invariant at the rule, "
          f"{added - cited} citing none")
    if added == 0:
        print("   VERDICT: empty — nothing was added in the range, so nothing was checked.")
    elif cited == added:
        print("   VERDICT: clean — every added hard rule cites an invariant at the rule.")
    else:
        print("   VERDICT: NOT clean — read each uncited line: a missing citation, an")
        print("            unregistered rule, or (template content) the parent's to register.")
    print("   ⚠ Only .md files are scanned; rules stated in .py/.json comments are not.")
    return 0


def _ledger_ids(text: str, prefix: str) -> set[str]:
    """Ids a registry *defines* — `- **<PREFIX>-NNN**` entries — not ids it merely cites."""
    return set(re.findall(r"^\s*-\s*\*\*(%s-\d{3})\*\*" % prefix, text, re.M))


def parent_invariants_text(corpus: Corpus, args) -> tuple[str | None, str]:
    """The parent's INVARIANTS.md at the pinned release, and where it came from."""
    if args.parent_invariants:
        path = Path(args.parent_invariants)
        return path.read_text(encoding="utf-8"), str(path)
    if args.offline:
        return None, "not read (--offline)"
    tag = corpus.template_release
    done = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github.raw",
         f"repos/{PARENT_DEVELOPMENT_REPOSITORY}/contents/{PARENT_INVARIANTS_PATH}?ref={tag}"],
        capture_output=True, text=True,
    )
    if done.returncode != 0 or not done.stdout.strip():
        return None, f"could not be fetched ({(done.stderr or 'empty response').strip()[:120]})"
    return done.stdout, f"{PARENT_DEVELOPMENT_REPOSITORY}:{PARENT_INVARIANTS_PATH}@{tag}"


def cmd_citations(corpus: Corpus, args) -> int:
    """Every INV-/KINV- id cited in the shipped Power resolves to a definition."""
    kinv_defined = _ledger_ids((corpus.repo / LEDGER_REL).read_text(encoding="utf-8"), "KINV")
    parent_text, parent_source = parent_invariants_text(corpus, args)
    inv_defined = _ledger_ids(parent_text, "INV") if parent_text else None

    cited: dict[str, list[str]] = collections.defaultdict(list)
    for path in corpus.markdown():
        for lineno, line in enumerate(corpus.lines(path), 1):
            for ident in set(ANY_ID.findall(line)):
                cited[ident].append(f"{corpus.rel(path)}:{lineno}")

    print("== invariant citations in the shipped Power resolve to a definition\n")
    print(f"   KINV registry: {LEDGER_REL} ({len(kinv_defined)} defined)")
    print(f"   INV registry:  {parent_source}"
          + (f" ({len(inv_defined)} defined)" if inv_defined is not None else ""))
    dangling, unverified, resolved = [], [], 0
    for ident in sorted(cited):
        registry = kinv_defined if ident.startswith("KINV-") else inv_defined
        if registry is None:
            unverified.append(ident)
        elif ident in registry:
            resolved += 1
        else:
            dangling.append(ident)
    for ident in dangling:
        sites = cited[ident]
        print(f"   DANGLING {ident}  cited at {', '.join(sites[:3])}{' …' if len(sites) > 3 else ''}")
    print(f"\n   {len(cited)} distinct id(s) cited: {resolved} resolved, {len(dangling)} dangling, "
          f"{len(unverified)} UNVERIFIED")
    if unverified:
        print(f"   ⛔ NOT clean: {len(unverified)} INV id(s) were not checked because the parent")
        print("     registry was unavailable. Pass --parent-invariants <file>, or run with network.")
    print("   ^ resolving proves the id EXISTS; only reading proves it is the RIGHT one for the")
    print("     claim beside it. A dangling INV in template content is parent-bound.")
    return 0


#: Backticked tokens that look like a skill or command name.
_SKILL_TOKEN = re.compile(r"`/?([a-z0-9]+(?:-[a-z0-9]+)+)`")
_SKILL_PATH = re.compile(r"\bskills/([a-z0-9]+(?:-[a-z0-9]+)+)/")
#: A slash command written as one: a backticked `/name`, alone or followed by its arguments.
#: Bare `/opt`, `/tmp`, `/api/...` are filesystem and URL paths, not commands.
_SLASH = re.compile(r"`/([a-z][a-z0-9-]*)(?:[ `])")


def cmd_references(corpus: Corpus, args) -> int:
    """Skill names nothing ships, and slash commands a Kiro Power cannot provide."""
    shipped = corpus.skill_names()
    template_skills = {
        Path(src).parts[3]
        for src in corpus.sources.values()
        if src and src.startswith("plugins/senzing-bootcamp/skills/") and len(Path(src).parts) > 4
    }
    print("== references to skills and commands\n")
    print(f"   {len(shipped)} skill(s) shipped; {len(template_skills)} template skill name(s) known")
    missing = collections.defaultdict(list)
    slash = collections.defaultdict(list)
    for path in corpus.markdown():
        for lineno, line in enumerate(corpus.lines(path), 1):
            where = f"{corpus.rel(path)}:{lineno}"
            for name in _SKILL_PATH.findall(line):
                if name not in shipped:
                    missing[name].append(where)
            for name in _SKILL_TOKEN.findall(line):
                looks_like_skill = name.startswith(("module-", "bootcamp-")) or name in template_skills
                if looks_like_skill and name not in shipped:
                    missing[name].append(where)
            for name in _SLASH.findall(line):
                slash[name].append(where)
    for name in sorted(missing):
        sites = missing[name]
        print(f"   NOT SHIPPED  {name:<38} {', '.join(sites[:2])}{' …' if len(sites) > 2 else ''}")
    print("\n   slash commands named (a Kiro Power ships none; the Kiro CLI has its own):")
    for name, sites in sorted(slash.items(), key=lambda kv: -len(kv[1]))[: args.top]:
        print(f"     /{name:<24} {len(sites):4d}  e.g. {sites[0]}")
    print(f"\n   {len(missing)} name(s) referenced that no shipped skill carries; "
          f"{len(slash)} distinct slash token(s)")
    print("   ^ leads. A name in a worked example, a template command the port represents as a")
    print("     trigger-phrase skill, or a Kiro CLI command (`/model`, `/effort`) is legitimate.")
    return 0


def _entries(text: str, pattern: str) -> list[tuple[str, str]]:
    return re.findall(
        r"^\s*- \*\*(%s)\*\*\s*—\s*(.+?)(?=\n\s*- \*\*(?:%s)\*\*|\n##|\Z)" % (pattern, pattern),
        text, re.M | re.S,
    )


ENUMERATION_SIGNALS = (
    ("exact count", re.compile(r"\bexactly (?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b", re.I)),
    ("closed list", re.compile(r"\bis (?:exactly|precisely)\b|\bthe following\b|\bconsists of\b"
                               r"|\bno other\b|\bonly these\b", re.I)),
    ("comma series", re.compile(r"`[^`]+`(?:(?:\s*,\s*|\s*,?\s*(?:and|or)\s+)`[^`]+`){2,}")),
)


def cmd_enumerations(corpus: Corpus, args) -> int:
    """Invariants that enumerate — the ones that go stale while still reading authoritative."""
    sources = [("KINV", LEDGER_REL, (corpus.repo / LEDGER_REL).read_text(encoding="utf-8"))]
    if args.parent_invariants:
        sources.append(("INV", args.parent_invariants,
                        Path(args.parent_invariants).read_text(encoding="utf-8")))
    print("== invariants that enumerate (stale-risk surface)\n")
    for prefix, where, text in sources:
        entries = _entries(text, r"%s-\d{3}" % prefix)
        found = 0
        print(f"   {where}")
        for ident, body in entries:
            body = " ".join(body.split())
            why = [label for label, pat in ENUMERATION_SIGNALS if pat.search(body)]
            if why:
                found += 1
                print(f"     {ident}  [{', '.join(why)}]  {body[:120]}")
        print(f"     {found} of {len(entries)} enumerate something\n")
    if not args.parent_invariants:
        print("   (the parent's INV registry was not read; pass --parent-invariants to include it)")
    print("   ^ check each enumeration against what the Power ships TODAY.")
    return 0


def _normalize(line: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", line.lower())


def cmd_duplication(corpus: Corpus, args) -> int:
    """Passages repeated across shipped files — where "fixed in one place" hides."""
    n = args.words
    index: dict[str, set[tuple[str, int]]] = collections.defaultdict(set)
    for path in corpus.markdown():
        for lineno, line in enumerate(corpus.lines(path), 1):
            words = _normalize(line).split()
            for i in range(len(words) - n + 1):
                index[" ".join(words[i:i + n])].add((corpus.rel(path), lineno))
    # Byte-identical files are deliberate mirrors — the kiro-hooks rule materializes one
    # authored tree at two destinations — so they repeat by construction and cannot drift.
    digest = {corpus.rel(p): p.read_bytes() for p in corpus.markdown()}
    shared = {s: locs for s, locs in index.items() if len({f for f, _ in locs}) > 1}
    pairs = collections.Counter()
    mirrored = set()
    for locs in shared.values():
        files = sorted({f for f, _ in locs})
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                if digest[files[i]] == digest[files[j]]:
                    mirrored.add((files[i], files[j]))
                    continue
                pairs[(files[i], files[j])] += 1
    print(f"== passages of {n}+ words appearing in more than one shipped file\n")
    if mirrored:
        print(f"   ({len(mirrored)} byte-identical mirror pair(s) skipped: they cannot drift)\n")
    for (a, b), count in pairs.most_common(args.top):
        oa, ob = corpus.owners.get(a, UNRECORDED), corpus.owners.get(b, UNRECORDED)
        print(f"   {count:4d} shared   {a} [{oa}]")
        print(f"                 {b} [{ob}]")
    print(f"\n   {len(shared)} repeated passages across {len(pairs)} file pair(s)")
    print("   ^ repetition required AT a step is INV-183, not redundancy. The finding is")
    print("     repetition that has DRIFTED. A kiro-owned file repeating template text is")
    print("     the likeliest drift: the template copy moves by rebuild and the authored one does not.")
    return 0


def cmd_size(corpus: Corpus, args) -> int:
    """Goldilocks measurements: where the definition is heaviest. A number, not a target."""
    rows = []
    for path in corpus.markdown():
        body = path.read_text(encoding="utf-8")
        rows.append((len(body.split()), len(body.splitlines()), corpus.rel(path), corpus.owner(path)))
    rows.sort(reverse=True)
    by_owner = collections.Counter()
    for words, _, _, owner in rows:
        by_owner[owner] += words
    print(f"== shipped markdown: {len(rows)} files, {sum(r[0] for r in rows):,} words "
          f"({', '.join(f'{o} {w:,}' for o, w in by_owner.most_common())})\n")
    for words, lines, name, owner in rows[:12]:
        print(f"   {words:>7,} words  {lines:5d} lines  [{owner:<8}] {name}")
    print("\n   ^ never cut rationale to move this number; the win is merging duplicated")
    print("     statements and moving a rule to where it is used.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

VIEWS = {
    "rules": cmd_rules,
    "since": cmd_since,
    "citations": cmd_citations,
    "references": cmd_references,
    "enumerations": cmd_enumerations,
    "duplication": cmd_duplication,
    "size": cmd_size,
}
#: `all` runs every view that needs no range; `since` is its own call.
ALL_VIEWS = ("rules", "citations", "references", "enumerations", "duplication", "size")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("view", choices=[*VIEWS, "all"])
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--uncited", action="store_true", help="rules: list only uncited rules")
    parser.add_argument("--ref", help="since: the git ref to diff from (default: the newest semver tag)")
    parser.add_argument("--parent-invariants", help="the parent's INVARIANTS.md at the pinned release")
    parser.add_argument("--offline", action="store_true", help="citations: do not fetch the parent registry")
    parser.add_argument("--words", type=int, default=12, help="duplication: passage length")
    parser.add_argument("--top", type=int, default=15, help="duplication/references: rows shown")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    corpus = Corpus(Path(args.repo).resolve())
    views = ALL_VIEWS if args.view == "all" else (args.view,)
    for index, name in enumerate(views):
        if index:
            print("\n" + "-" * 78 + "\n")
        VIEWS[name](corpus, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
