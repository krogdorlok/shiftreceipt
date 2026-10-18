# SWEEP: whole-project edge-case audit (runs in parallel with the builder; repeat until clean)
Scope: every file, not only the diff: agent.py, extract.py, notice.py, rules.py, diff.py, parser.py, db.py.
Specs: CLAUDE.md invariants, CORE.md, prompts/M1-M5.md, prompts/CORE-FIX.md (City guidance wins over M-specs).
Known, accepted limitations (do not report unless they produce a wrong amount in a common case):
Mon-Sun work periods, one hourly rate per worker, coverage self-reported, card schema unverified (CARDS=0 kill switch),
pending images kept in memory only (lost on restart), "Advance Notice" box never ticked automatically.

Hunt, with a failing test for each real bug (tests/review/test_sweep_<n>.py, offline, Gemini/httpx/SMTP mocked):
- Money: every FAQ table row, thresholds at 14/15/16 min, 13/14 days, 9:59/10:00 rest, overnight and DST
  (Nov 1 2026, Mar 8 2026), year wrap, rate 1 cent and $200, rounding, totals by rule, due_lines on the shift day.
- Flow (agent.py via a fake ctx): every command in every state, out of order (CONFIRM before SCHEDULE, ANSWER
  before CONFIRM, SEND before receipt), GOT/EDIT/DROP edge dates, third and fourth versions, v3 cancelling,
  re-upload of an older version, RECEIPT with open questions, OT, MODE switches mid-flow, pasted multi-line input.
- Isolation: two senders interleaved in every step, SEND of another sender's id, RESET scope, same msg_id from
  two senders, concurrency (two messages from one sender at once).
- Hostile input: injection text in NAME/STORE/SCHEDULE location reaching the PDF or email headers (CRLF),
  2000+ char messages, unicode, empty content list, unknown content types, card JSON with wrong types.
- Failure: Gemini down/slow/bad JSON, SMTP failure then retry, daily cap, restart mid-flow (module reload, same DB).
- Wording: every user-facing string: "may be owed", "Not legal advice" where amounts appear, never "you are owed",
  never "files your complaint", no em dashes.
Severity per AGENTS.md. Report at most the 8 most important findings per round, BLOCKER first.
