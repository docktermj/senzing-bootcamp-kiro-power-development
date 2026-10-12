#!/usr/bin/env python3
"""Escalation loop — a local issue closes when the fix it escalated has LANDED here (R7).

    escalations.py mark <local-issue> --parent <parent-issue>   [--apply]
    escalations.py check [--target <tag>] [--pinned <tag>]       [--apply]

`escalate-to-parent` files a curriculum problem upstream; this file is how the local
tracking issue learns the fix arrived. Dry run by default: every command prints exactly
what it would write and writes nothing until `--apply`, which the skills run only after
the maintainer approves the printed text (INV-314).

The marker is a LABEL, `awaiting-parity`, because a convention that lives only in prose
does not survive the first maintainer who edits the issue. The parent issue it waits on
is recorded in a comment this tool writes, carrying a machine-readable line:

    <!-- awaiting-parity: docktermj/senzing-bootcamp-claude-plugin-development#112 -->

When does the local issue close?
--------------------------------
⛔ **Not when the parent issue closes.** A parent issue closed but not yet released has
reached no bootcamper, and this port reads a tag, never the parent's `main` (R2).

⛔ **Not when `parity-check` merely reports a tag that contains the fix**, either. That tag
is a *target*; the Kiro Power still carries the defect until the update to it lands.

The issue closes when the fix is contained in the parent release **this port is pinned
to** — `PARENT_VERSION` in the committed Power. A fix is "contained" when the parent issue
was closed as completed by a commit (a merged closing pull request's merge commit, or the
commit a `closed` event names) and every such commit is an ancestor of that tag
(GitHub compare: the tag is `ahead` of, or `identical` to, the commit).

So `check` sorts every open `awaiting-parity` issue into exactly one verdict:

    arrived           the pinned release contains the fix          -> close, naming the tag
    in-target         --target contains it, the pinned one does not -> say so; stays open
    pending-release   fixed in the parent, in no release checked yet -> stays open
    pending           the parent issue is still open                -> stays open
    declined          the parent closed it as not planned/duplicate -> surface; NEVER close
    undetermined      closed as completed, but no fix commit found,
                      or the parent reference is missing/unreadable -> surface; never close

`--pinned` points the check at a pinned release that is not committed yet — the parity
pull request's own `PARENT_VERSION` — so `implement-github-issue` can put
`Closes #<n>` in that pull request for each `arrived` issue. Merging the update is then
what closes them: the issue closes on the parity **landing**, not on a report of it.

`--apply` closes `arrived` issues with a comment naming the tag and the fix commit,
comments once on `in-target` issues, and labels `declined` and `undetermined` issues
`needs-decision` with a comment saying why. It never closes anything else.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Iterable, Sequence  # noqa: E402

ENGINE_ROOT = Path(__file__).resolve().parent
REPO = ENGINE_ROOT.parent.parent
THIS_REPOSITORY = "docktermj/senzing-bootcamp-kiro-power-development"
PARENT_REPOSITORY = "docktermj/senzing-bootcamp-claude-plugin-development"
PLUGIN = REPO / "powers" / "senzing-bootcamp" / "plugin.json"

LABEL_AWAITING = "awaiting-parity"
LABEL_DECISION = "needs-decision"
LABELS = {
    LABEL_AWAITING: ("1d76db", "Escalated to the parent; closes when the fix lands in the pinned PARENT_VERSION"),
    LABEL_DECISION: ("d93f0b", "The parent declined, or the loop cannot tell whether the fix landed; a human decides"),
}

MARKER = re.compile(r"<!--\s*awaiting-parity:\s*(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)\s*-->")
#: Written once per issue and target, so a re-run comments nothing new.
IN_TARGET_MARKER = "<!-- parity-in-target: {tag} -->"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

ARRIVED = "arrived"
IN_TARGET = "in-target"
PENDING_RELEASE = "pending-release"
PENDING = "pending"
DECLINED = "declined"
UNDETERMINED = "undetermined"
VERDICTS = (ARRIVED, IN_TARGET, PENDING_RELEASE, PENDING, DECLINED, UNDETERMINED)


# ---------------------------------------------------------------------------
# The pure decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParentState:
    """What the parent issue says about the fix."""

    state: str  # "open" | "closed"
    reason: str | None  # "completed" | "not_planned" | "duplicate" | None
    fix_commits: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verdict:
    issue: int
    title: str
    parent: str | None
    verdict: str
    reason: str
    tag: str | None = None
    commits: tuple[str, ...] = ()


def classify(
    issue: int,
    title: str,
    parent: str | None,
    state: ParentState | None,
    *,
    pinned: str,
    target: str | None,
    contains: Callable[[str, str], bool],
) -> Verdict:
    """One verdict per issue. Pure, except for `contains(commit, tag)`, which is injected.

    Closing is the only irreversible action, so every path that cannot *prove* the fix is
    in the pinned release ends somewhere other than `arrived`.
    """
    if parent is None or state is None:
        return Verdict(issue, title, parent, UNDETERMINED,
                       "no readable parent-issue marker on this issue; escalate-to-parent writes one")
    if state.state == "open":
        return Verdict(issue, title, parent, PENDING, f"{parent} is still open")
    if state.reason in ("not_planned", "duplicate"):
        return Verdict(issue, title, parent, DECLINED,
                       f"{parent} was closed as {state.reason.replace('_', ' ')}: the parent decided "
                       "not to fix it, so this port still carries the defect and a human decides "
                       "what happens to it here")
    if not state.fix_commits:
        return Verdict(issue, title, parent, UNDETERMINED,
                       f"{parent} was closed as completed but names no fix commit (no merged closing "
                       "pull request and no closing commit), so whether a release contains it "
                       "cannot be established")
    if all(contains(sha, pinned) for sha in state.fix_commits):
        return Verdict(issue, title, parent, ARRIVED,
                       f"the pinned PARENT_VERSION {pinned} contains every fix commit of {parent}",
                       tag=pinned, commits=state.fix_commits)
    if target and all(contains(sha, target) for sha in state.fix_commits):
        return Verdict(issue, title, parent, IN_TARGET,
                       f"parent release {target} contains the fix; the pinned {pinned} does not, so "
                       "it closes when the update to it lands",
                       tag=target, commits=state.fix_commits)
    checked = f"{pinned}" + (f" or {target}" if target else "")
    return Verdict(issue, title, parent, PENDING_RELEASE,
                   f"{parent} is fixed in the parent but not in {checked} yet",
                   commits=state.fix_commits)


# ---------------------------------------------------------------------------
# GitHub, through `gh`
# ---------------------------------------------------------------------------


def gh(*args: str, input_text: str | None = None) -> str:
    done = subprocess.run(["gh", *args], input=input_text, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {done.stderr.strip()}")
    return done.stdout


def parent_state(repository: str, number: int) -> ParentState:
    owner, name = repository.split("/", 1)
    query = """query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n){issue(number:$i){
      state stateReason
      closedByPullRequestsReferences(first:20,includeClosedPrs:true){nodes{merged mergeCommit{oid}}}
      timelineItems(itemTypes:[CLOSED_EVENT],last:5){nodes{... on ClosedEvent{closer{__typename ... on Commit{oid}}}}}
    }}}"""
    data = json.loads(gh("api", "graphql", "-f", f"query={query}", "-F", f"o={owner}",
                         "-F", f"n={name}", "-F", f"i={number}"))
    issue = data["data"]["repository"]["issue"]
    commits = [n["mergeCommit"]["oid"] for n in issue["closedByPullRequestsReferences"]["nodes"]
               if n.get("merged") and n.get("mergeCommit")]
    for node in issue["timelineItems"]["nodes"]:
        closer = (node or {}).get("closer") or {}
        if closer.get("__typename") == "Commit" and closer.get("oid"):
            commits.append(closer["oid"])
    reason = (issue.get("stateReason") or "").lower() or None
    return ParentState(state=issue["state"].lower(), reason=reason,
                       fix_commits=tuple(dict.fromkeys(commits)))


def tag_contains(repository: str) -> Callable[[str, str], bool]:
    cache: dict[tuple[str, str], bool] = {}

    def contains(commit: str, tag: str) -> bool:
        if (commit, tag) not in cache:
            status = gh("api", f"repos/{repository}/compare/{commit}...{tag}", "-q", ".status").strip()
            cache[(commit, tag)] = status in ("ahead", "identical")
        return cache[(commit, tag)]

    return contains


def awaiting_issues() -> list[dict[str, Any]]:
    out = gh("issue", "list", "--repo", THIS_REPOSITORY, "--state", "open", "--label", LABEL_AWAITING,
             "--limit", "200", "--json", "number,title")
    return json.loads(out)


def parent_reference(number: int) -> str | None:
    """The newest marker on the issue — comments first (the tool writes there), then the body."""
    data = json.loads(gh("issue", "view", str(number), "--repo", THIS_REPOSITORY,
                         "--json", "body,comments"))
    texts = [c.get("body") or "" for c in data.get("comments", [])][::-1] + [data.get("body") or ""]
    for text in texts:
        found = list(MARKER.finditer(text))
        if found:
            last = found[-1]
            return f"{last.group('repo')}#{last.group('num')}"
    return None


def has_comment(number: int, needle: str) -> bool:
    data = json.loads(gh("issue", "view", str(number), "--repo", THIS_REPOSITORY, "--json", "comments"))
    return any(needle in (c.get("body") or "") for c in data.get("comments", []))


def pinned_version() -> str:
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    return str(plugin["extensions"]["com.senzing.bootcamp"]["PARENT_VERSION"])


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def ensure_labels() -> None:
    existing = {item["name"] for item in json.loads(
        gh("label", "list", "--repo", THIS_REPOSITORY, "--limit", "200", "--json", "name"))}
    for name, (color, description) in LABELS.items():
        if name not in existing:
            gh("label", "create", name, "--repo", THIS_REPOSITORY, "--color", color,
               "--description", description)


def mark_comment(parent: str) -> str:
    return (
        f"Escalated to the parent as {parent}. This issue is **awaiting parity**: it closes when "
        "the fix is contained in the parent release this port is pinned to (`PARENT_VERSION`), "
        "confirmed by `escalations.py check` — not when the parent issue closes.\n\n"
        f"<!-- awaiting-parity: {parent} -->"
    )


def cmd_mark(args) -> int:
    parent = f"{PARENT_REPOSITORY}#{args.parent}"
    body = mark_comment(parent)
    print(f"would label #{args.issue} `{LABEL_AWAITING}` and comment:\n\n{body}\n")
    if not args.apply:
        print("Dry run: nothing was written. Re-run with --apply after approval.")
        return 0
    ensure_labels()
    gh("issue", "edit", str(args.issue), "--repo", THIS_REPOSITORY, "--add-label", LABEL_AWAITING)
    gh("issue", "comment", str(args.issue), "--repo", THIS_REPOSITORY, "--body-file", "-", input_text=body)
    print(f"marked #{args.issue} awaiting parity on {parent}")
    return 0


def close_comment(verdict: Verdict) -> str:
    commits = ", ".join(f"`{sha[:12]}`" for sha in verdict.commits)
    return (
        f"The fix escalated as {verdict.parent} has landed: the pinned parent release "
        f"`PARENT_VERSION` **{verdict.tag}** contains its fix commit(s) {commits}. "
        "Closing (R7: an escalation closes on the parity landing, not when the parent issue closes)."
    )


def decision_comment(verdict: Verdict) -> str:
    return f"⚠️ Needs a decision here: {verdict.reason}. Not closed. <!-- {LABEL_DECISION}: {verdict.verdict} -->"


def cmd_check(args) -> int:
    pinned = args.pinned or pinned_version()
    for tag in filter(None, (pinned, args.target)):
        if not SEMVER.match(tag):
            print(f"refusing: {tag!r} is not a bare release tag (R2: never main, never HEAD)", file=sys.stderr)
            return 2
    contains = tag_contains(PARENT_REPOSITORY)
    verdicts = []
    for item in awaiting_issues():
        parent = parent_reference(item["number"])
        state = None
        if parent:
            repo, _, num = parent.partition("#")
            try:
                state = parent_state(repo, int(num))
            except (RuntimeError, KeyError, TypeError) as error:
                print(f"  #{item['number']}: could not read {parent} ({error})", file=sys.stderr)
        verdicts.append(classify(item["number"], item["title"], parent, state,
                                 pinned=pinned, target=args.target, contains=contains))

    print(f"== escalations awaiting parity: pinned PARENT_VERSION {pinned}"
          + (f", target {args.target}" if args.target else "") + "\n")
    for v in verdicts:
        print(f"   #{v.issue:<5} {v.verdict:<16} {v.parent or '(no parent marker)'}  {v.title}")
        print(f"          {v.reason}")
    if not verdicts:
        print("   none — no open issue carries the awaiting-parity label")
    arrived = [v for v in verdicts if v.verdict == ARRIVED]
    if arrived and args.pinned:
        print("\n   For the parity pull request body (merging it is what lands the fix):")
        for v in arrived:
            print(f"     Closes #{v.issue}")

    print("\n   Writes --apply would make:")
    actions = []
    for v in verdicts:
        if v.verdict == ARRIVED and not args.pinned:
            actions.append((v, "close", close_comment(v)))
        elif v.verdict == IN_TARGET and not has_comment(v.issue, IN_TARGET_MARKER.format(tag=v.tag)):
            actions.append((v, "comment",
                            f"Parent release {v.tag} contains the fix for {v.parent}; this closes when the "
                            f"update to {v.tag} lands. {IN_TARGET_MARKER.format(tag=v.tag)}"))
        elif v.verdict in (DECLINED, UNDETERMINED):
            actions.append((v, "needs-decision", decision_comment(v)))
    for v, kind, body in actions:
        print(f"     #{v.issue} {kind}: {body}")
    if not actions:
        print("     none")
    if args.pinned and arrived:
        print("   (--pinned names an unlanded release, so nothing is closed here: the pull request closes them)")
    if not args.apply or not actions:
        if actions:
            print("\nDry run: nothing was written. Re-run with --apply after the maintainer approves each.")
        return 0
    ensure_labels()
    for v, kind, body in actions:
        gh("issue", "comment", str(v.issue), "--repo", THIS_REPOSITORY, "--body-file", "-", input_text=body)
        if kind == "close":
            gh("issue", "close", str(v.issue), "--repo", THIS_REPOSITORY, "--reason", "completed")
            gh("issue", "edit", str(v.issue), "--repo", THIS_REPOSITORY, "--remove-label", LABEL_AWAITING)
        elif kind == "needs-decision":
            gh("issue", "edit", str(v.issue), "--repo", THIS_REPOSITORY, "--add-label", LABEL_DECISION)
        print(f"   #{v.issue}: {kind} done")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("mark", help="mark a local issue as awaiting parity on a parent issue")
    mk.add_argument("issue", type=int)
    mk.add_argument("--parent", type=int, required=True, help=f"the issue number in {PARENT_REPOSITORY}")
    mk.add_argument("--apply", action="store_true")
    ck = sub.add_parser("check", help="sort every awaiting-parity issue into one verdict")
    ck.add_argument("--target", help="the parent tag parity-check is comparing against")
    ck.add_argument("--pinned", help="a not-yet-landed PARENT_VERSION (a parity pull request's)")
    ck.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    return cmd_mark(args) if args.cmd == "mark" else cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
