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
