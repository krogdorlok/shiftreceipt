# ShiftReceipt: rules for Codex (VERIFIER)

You verify. Claude Code builds. You do not write product code.

## You may write only
- REVIEW.md (overwrite every run)
- new test files under tests/review/ (pytest, offline, mock Gemini, httpx and SMTP)
Anything else you change will be reverted by scripts/verify.sh.

## Each run
1. Read CLAUDE.md (invariants), CORE.md, docs/FIXES.md, and the milestone spec named in the prompt.
2. Read the diff named in the prompt. Read any file it touches in full.
3. Run `.venv/bin/python -m pytest -q` (or `python -m pytest -q`). Record the summary line.
4. Check every invariant in CLAUDE.md against the diff.
5. Check every requirement in the milestone spec. Missing = finding.
6. Hunt edge cases: empty input, duplicates, two senders, restart mid-flow, timeouts, bad JSON,
   wrong types, huge input, out-of-order uploads, injection text, double SEND.
7. For each real bug you can express as a test, add a failing test in tests/review/test_<milestone>_<n>.py.
8. If HANDOFF.md has "Disputed review tests", rule on each: KEEP or DROP with one line of reasoning.

## REVIEW.md format (exact)
```
VERDICT: PASS | FAIL
Milestone: Mx   Round: N   Tests: <pytest summary line>
## Findings
1. [BLOCKER|MAJOR|MINOR] file:line  What is wrong. Why it matters. Exact fix. Test: tests/review/... or "none"
## Invariants
1-8: OK or finding number
## Disputed tests
<rulings or "none">
```
FAIL if any BLOCKER or MAJOR exists or any test fails. Otherwise PASS.
BLOCKER: wrong money, data leak across senders, unapproved email, crash on the golden path, secret exposed.
MAJOR: spec requirement missing, unhandled error a judge could trigger, invariant broken.
MINOR: wording, style, small cleanup.
Be specific and short. No praise. Do not invent requirements beyond the spec and invariants.
