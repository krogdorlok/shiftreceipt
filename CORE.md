# ShiftReceipt core (frozen contracts, 82 tests)

Run: `python3 -m pip install -r requirements.txt && python3 -m pytest -q`

| File | What | Owner from now |
| --- | --- | --- |
| models.py | Shift, ScheduleVersion, ChangeEvent, Answers, Coverage, LedgerLine, nearest_date | frozen, change only with team agreement |
| diff.py | diff(prev, curr) -> list[ChangeEvent] | builder |
| rules.py | evaluate(), rest_lines(), missing_answers(), total(), cure_deadline() | builder |
| parser.py | parse(text) -> Command: card JSON, typed SCHEDULE block, typed command, then planner prose | builder |
| db.py | SQLite: dedupe msgs, state per sender, versions (dedupe by hash, ordered by learned_at), answers, notices (atomic claim, retry on SMTP fail, 2/day cap), reset | builder |
| fixtures/ | v1, v2, v3 demo week Oct 19-25 2026 | T1 draws the screenshots to match |

Golden demo (test_demo_receipt_matches_pitch): v1 learned Oct 4, v2 learned Oct 18, $20/h ->
Tue moved $20, Thu 3 h cut $30, Sun 2 h added $20, Sat clopening $80 = $150 ($70 schedule-change pay now, $80 rest premium only if Sat is worked). v3 cancels Sunday: +$80.

Still to build (one builder, see ShiftReceipt_ONE_LAPTOP.md): agent.py, extract.py, notice.py.
Agent flow: ack -> first_time(msg_id) -> parse or image -> state machine in db -> diff consecutive
confirmed versions -> missing_answers -> Q<n> -> evaluate + rest_lines on latest version -> receipt
-> create_notice -> SEND n -> claim_notice -> render + send -> finish_notice -> cure_deadline.
