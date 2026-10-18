# CORE-FIX: rules corrected to City guidance (human approved editing rules.py, diff.py, tests)
Sources (City of LA OWS): Fair Work Week FAQ (Nov 2023) items 36, 50, 52, 53, 65 and the predictability pay table;
Training Module 2 and 3, Scenario 1 (Mon 8 AM -> Tue 12 PM = 2 h).

1. 14-day notice is measured from the start of the Work Period, not from each changed shift.
   rules.period_start(day) = Monday of that week (assumption: Mon-Sun work periods). is_late uses it, LA date.
   Week Oct 19-25: learned Oct 5 -> not late; learned Oct 6 -> late, for every shift in the week.
2. Predictability pay per the FAQ table: 1 h per change to date, time or location. When hours change, the
   time change is not counted again. Added hours > 15 min: 1 h + 1 h per date/location change.
   Cut >= 15 min or cancel: half pay for lost hours + 1 h per date/location change. moved_and_cut and
   moved_and_added are now paid (not needs_review); moved_and_cut asks the misconduct question.
   A location counts as changed only if both versions name one. A move with no countable change: needs_review.
3. diff: a cancel and an add left over in the same ISO week may be one move with new hours (FAQ: one change),
   so both become needs_review (no amount) instead of cancel + add (overpays).
4. rules.total(lines, rules=None) can total by rule; rules.due_lines(lines, today) keeps the rest premium only
   for shifts already past (owed only if worked). cure_deadline counts 15 days from the employer's receipt.
Golden demo unchanged in cents: $70 schedule-change pay (R2+R3+R4) + $80 rest premium (R6, only if worked).
Tests: tests/test_rules.py (FAQ table rows, work period boundary, due_lines), tests/test_diff.py.
