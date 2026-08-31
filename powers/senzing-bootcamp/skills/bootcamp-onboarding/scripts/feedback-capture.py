#!/usr/bin/env python3
"""UserPromptSubmit hook: "to capture bootcamp feedback and verbosity changes".

Only active during a bootcamp (a config/bootcamp_progress.json file exists in the
working directory). If the bootcamper's message asks to give feedback or to change
verbosity, inject guidance so those "at any time" requests are handled the same way
anywhere in the bootcamp. Emits nothing otherwise, so the Power never alters
unrelated Kiro sessions.

Cross-platform: invoked in exec form (``python3 <path>``) so no shell is required.
"""
import json
import os
import re
import sys


def plugin_version():
    """The version of the Power THIS hook ships in, resolved from the hook's own path.

    Kiro substitutes ``${PLUGIN_ROOT}`` in the hook's ``args``, but not
    inside the text the hook injects -- so handing the guide that path leaves it to
    resolve the manifest with a variable that may be unset, and on a machine carrying
    two Power roots (an installed Power plus a clone, or an un-removed upgrade) a
    search for `plugin.json` then answers with the wrong checkout's version. This file
    always knows where it lives, so it answers with the value instead of a path.

    Returns "Unknown" rather than guessing when the manifest cannot be read or parsed.
    """
    manifest = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        os.pardir, os.pardir,  # skills/<skill>/scripts/ -> Power root
        "plugin.json",
    )
    try:
        with open(manifest, encoding="utf-8") as handle:
            version = json.load(handle).get("version")
    except (OSError, ValueError):
        return "Unknown"
    return version.strip() if isinstance(version, str) and version.strip() else "Unknown"


raw = sys.stdin.read()

# Gate: outside a bootcamp, do nothing at all.
if not os.path.isfile(os.path.join("config", "bootcamp_progress.json")):
    sys.exit(0)

# The prompt text is what we inspect; fall back to the raw payload if it is not JSON.
try:
    prompt = json.loads(raw).get("prompt", "")
except (ValueError, AttributeError):
    prompt = raw
lower = prompt.lower()

# ⛔ THE TWO HALVES OF THIS VOCABULARY ARE NOT SYMMETRIC, AND THAT IS DELIBERATE.
#
# Widening this pattern looks like a free win and is not. Modules 5-7 have the bootcamper
# writing and debugging *their own* loader, mapper and query code, so in this bootcamp
# "I found a bug", "something is broken" and "this is wrong" overwhelmingly mean THEIR
# code, not the Power. Injecting the feedback workflow there is not a harmless false
# positive: it prepends an instruction to open a feedback entry, present a banner and
# gather structured feedback on top of a turn where the bootcamper wants their traceback
# explained. A missed capture is far cheaper than a spurious one (INV-054's reasoning by
# analogy), because the workflow is still reachable by `/bootcamp-feedback` and by
# feedback.md, while a derailed debugging turn is not recoverable.
#
# So:
#   * UNAMBIGUOUS - the word "feedback" in any construction, or bug/issue/problem/broken
#     language that NAMES the bootcamp, plugin, module or tutorial. Widen aggressively.
#   * AMBIGUOUS - bare bug/broken/wrong/problem with no such referent. Must NOT trigger.
#
# ⛔ Do not "fix" a miss by deleting that distinction. The regex will be edited again; the
# reasoning above is the part that will not be rediscovered.

#: Verbs that make "feedback" a request to give it rather than a mention of the word.
_GIVE = r"(?:give|giving|gave|have|having|has|got|send|sending|submit|submitting|share|sharing|" \
        r"provide|providing|offer|offering|leave|leaving|report|reporting|pass|passing|add|adding)"
#: A short qualifier window, so an interposed word does not defeat the match. This is the
#: one-word gap that made `I have feedback` hit and `I have some feedback about module 5`
#: miss: the old pattern required the pair to be adjacent.
_GAP = r"(?:\W+\w+){0,3}?\W+"
#: Words that attribute a fault to the bootcamp rather than to the bootcamper's own code.
#: ⛔ Deliberately does NOT include "this step", "these instructions" or "this skill". In
#: Modules 5-7 "this step is wrong" is far more often the bootcamper's own work in
#: progress than a defect in the Power, so those phrasings stay in the ambiguous half.
#: The referents here are the four the Power can actually be blamed by name for.
_OURS = r"(?:bootcamp|plugin|senzing bootcamp|this tutorial|tutorial|module \d+)"

FEEDBACK = re.compile(
    # The noun, in any construction: "bootcamp feedback", "I have some feedback about
    # module 5", "I'd like to give feedback", "can I give you some feedback", "sharing
    # feedback". Either order, since both "give feedback" and "feedback to give" occur.
    r"(?:bootcamp|plugin|power) feedback"
    r"|feedback (?:on|about|for|regarding) (?:the )?" + _OURS +
    r"|" + _GIVE + _GAP + r"feedback"
    r"|feedback" + _GAP + _GIVE +
    # An explicit report, already framed as one by the user.
    r"|report (?:an? )?(?:issue|bug|problem|defect)"
    # Fault language WITH a bootcamp/plugin referent - the attributed half. Kept narrow:
    # the referent must appear near the fault word, not merely somewhere in the prompt.
    r"|(?:bug|issue|problem|defect|broken|wrong|error)(?:\W+\w+){0,6}?\W+" + _OURS +
    r"|" + _OURS + r"(?:\W+\w+){0,6}?\W+(?:is |are |seems? )?(?:bug|issue|problem|defect|"
    r"broken|wrong)"
)

VERBOSITY = re.compile(
    # Same qualifier tolerance, lower stakes: verbosity is re-adjustable at any time and
    # carries no consent or durability guarantee, so a false positive is self-correcting.
    r"change verbosity|more detail|less detail|more code walkthrough|"
    r"too verbose|too terse|more verbose|less verbose|"
    r"(?:be|answer|reply|respond|make it|keep it)" + _GAP +
    r"(?:more |less |)(?:concise|verbose|detailed|wordy|brief|terse|short|shorter|"
    r"longer|succinct)|"
    r"(?:shorter|longer|briefer|more concise|less wordy|more wordy)\W+"
    r"(?:answers?|replies|responses?|explanations?)"
)

ctx = ""
if FEEDBACK.search(lower):
    ctx = (
        "The bootcamper is submitting bootcamp feedback. Follow the bootcamp "
        "feedback workflow (the feedback.md file in the bootcamp-onboarding skill): "
        "begin with the pinned BOOTCAMP FEEDBACK entry banner and end with the "
        "FEEDBACK SAVED exit banner (see feedback.md for the verbatim banner wording); "
        "silently capture as much relevant context as possible (the time; the Power "
        "version, which is " + plugin_version() + " -- already resolved from the running "
        "plugin, so record it as given and do NOT go looking for a plugin.json; "
        "current_module, current_step, and "
        "completed modules from config/bootcamp_progress.json; the recent questions "
        "asked and the bootcamper's responses; what the Power was doing behind the "
        "scenes; the observed problem; the expected behavior per the active "
        "hooks/skills; and why expected did not match actual) -- never ask extra "
        "questions, and record \"Unknown\" when a source is missing. Then gather the "
        "feedback one leading question at a time. APPEND (never overwrite) a "
        "formatted entry to docs/feedback/SENZING_BOOTCAMP_PLUGIN_FEEDBACK.md, "
        "creating that file with its header if it does not exist; then verify the "
        "entry landed (re-read and re-append if missing) before telling the "
        "bootcamper it was saved (INV-067). Triage whether the issue is in this "
        "Power or in the Senzing MCP server (feedback.md Step 2b) and record the "
        "verdict in the entry's Routing field -- every entry is saved locally "
        "whatever the verdict (INV-015). Only for an mcp-server/both verdict, and "
        "only after the local entry is confirmed saved, offer ONCE to forward it via "
        "the MCP server's submit_feedback tool, showing the exact message first and "
        "stripping anything identifying (INV-065); never send anything external "
        "without that yes. When done, "
        "return the bootcamper to exactly where they left off without making them "
        "re-explain their context."
    )
elif VERBOSITY.search(lower):
    ctx = (
        "The bootcamper wants to change the bootcamp's verbosity. Update the "
        "verbosity settings in config/bootcamp_preferences.yaml per the bootcamp "
        "ground rules, confirm the new setting in one sentence, then continue from "
        "where they left off. This is not a gate and must not interrupt the current "
        "step's pending question."
    )

if ctx:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": ctx,
        }
    }))
sys.exit(0)
