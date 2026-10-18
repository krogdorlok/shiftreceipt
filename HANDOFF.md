# Handoff log (Claude Code appends after every milestone)

## Core (done before M1)
models, diff, rules, parser, db, fixtures, 88 tests. Tag: core-verified.

## Core bug
none

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
