# ShiftReceipt: rules for Claude Code (BUILDER)

You build. Codex verifies. You never mark your own work verified.

## Project
Worker-side agent for the LA Fair Work Week Ordinance, running in ASI:One (Fetch.ai uAgents, Chat Protocol).
Built during LA Hacks AI Hackathon, Oct 17-18 2026. Specs: docs/PLAN.md, docs/ONE_LAPTOP.md, docs/FIXES.md, CORE.md.
Hard deadline: feature freeze 9:00 AM PDT, submit 11:00 AM PDT.

## Frozen files (do not edit without the human saying so)
models.py, diff.py, rules.py, parser.py, db.py, tests/test_*.py, fixtures/*.
If a frozen file has a bug: write it in HANDOFF.md under "Core bug", propose the fix, stop and ask.

## Invariants (Codex checks every one)
1. Gemini only extracts shifts. Money, dates owed and rule decisions come only from rules.py.
2. Every ledger line has a rule id and a citation. Money is integer cents.
3. No amount without COVER answers and the change questions for that change.
4. Nothing is emailed unless the same sender typed SEND <id> and db.claim_notice returned True.
5. Every db call passes sender. Never store images, only sha256. Never log emails, images or full messages.
6. User text says "may be owed" and "Not legal advice". Never "you are owed", never "files your complaint". No em dashes.
7. The handler acknowledges first and never blocks: Gemini, httpx, SMTP and PDF work run in asyncio.to_thread.
8. Secrets only from .env. Never print them, never commit .env or *.db.

## Milestones (one at a time, in order)
M1 agent skeleton -> M2 extract.py -> M3 full chat flow -> M4 notice + email -> M5 cards, manager mode, README.
Spec for each: prompts/M1.md ... prompts/M5.md. Build only the milestone the human names.

## Feedback loop (run this yourself at the end of every milestone)
1. `.venv/bin/python -m pytest -q` until green. Paste the summary line.
2. `git add -A && git commit -m "Mx: build"`.
3. Run `scripts/verify.sh Mx` with a 10 minute timeout. It runs Codex, which writes REVIEW.md.
4. Read REVIEW.md.
   - VERDICT: PASS -> `git tag Mx-verified`, append to HANDOFF.md, stop and report.
   - VERDICT: FAIL -> fix every BLOCKER and MAJOR (MINOR only if under 5 minutes),
     commit "Mx: fix round N", go to step 3.
5. Max 3 rounds. After round 3 still FAIL: stop and report the open findings to the human. Do not loop further.
6. Tests Codex adds in tests/review/ are the spec. You may change one only if it is provably wrong:
   explain why in HANDOFF.md under "Disputed review tests" and let Codex rule on it next round.
7. If verify.sh exits 2 (Codex unavailable): tell the human, who will run Codex by hand with prompts/verify.md.

## Report format at the end of each milestone
- What was built (files)
- Test summary line
- Codex verdict and rounds used
- "Needs human check" list: exact steps to try in ASI:One, with expected replies
