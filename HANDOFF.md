# Handoff log (Claude Code appends after every milestone)

## Core (done before M1)
models, diff, rules, parser, db, fixtures, 88 tests. Tag: core-verified.

## Core bug
1. 14-day notice measured from each shift; City measures from the start of the Work Period (FAQ 36, 50, 52).
2. Every move paid 1 h; City pays 1 h per date/time/location change (FAQ table, Module 3 Scenario 1).
3. Same-week cancel + add with new hours overpaid; now needs_review.
4. Rest premium counted as owed before the shift is worked; cure period runs from employer's receipt.
Human approved the fix (Oct 18, 5:15 AM). Fixed on branch core-fix, spec prompts/CORE-FIX.md.
CORE-FIX round 4 approved by the human (Oct 18) after round 3 FAIL: a week with a changed multi-shift day is all needs_review.
Final rule (human said "do it", Oct 18 5:40 AM, no 5th round): 2+ days in a week with a changed start/location are needs_review. Merged without a Codex PASS; round 4 test passes. M3 review re-checks diff.py/rules.py.

## Disputed review tests
none

## M1 (verified, 3 rounds)
agent.py (chat protocol, ack first, per-sender dedupe, image download with manual redirects, 10 s / 10 MB caps),
tests/test_agent_m1.py, README_AGENT.md, python-dotenv in requirements. verify.sh: codex 0.162 flags, stdin closed.
Needs human check: real AGENT_SEED in .env, `.venv/bin/python agent.py`, connect Mailbox, send a demo screenshot.

## M2 (verified, 3 rounds)
extract.py: Gemini schema is shifts only (ambiguous required), Python sets year (nearest_date), drops >60 days,
end==start, >16 h, ambiguous rows (named in warnings), duplicate rows; empty output -> unreadable.
One retry on timeout/5xx, SDK-internal retries off. CLI: python extract.py img.png "Maria Lopez".
Needs human check: GEMINI_API_KEY in .env, run the CLI on assets/demo v1, v2, v3, team_two_people (only Maria's
3 shifts) and not_a_schedule (unreadable); output must match fixtures/v1..v3.json.
