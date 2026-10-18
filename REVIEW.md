VERDICT: FAIL
Milestone: CORE-FIX   Round: 2   Tests: 2 failed, 95 passed in 0.12s
## Findings
1. [BLOCKER] diff.py:48  Two five-hour shifts swapping days are paired by day, producing $80 for time and location changes when pairing by shift produces $40 for date changes. Detect ambiguous cross-day matches before same-day pairing and mark affected changes needs_review. Test: tests/review/test_core_fix_4.py
2. [MAJOR] rules.py:64  A move with no countable change is needs_review, but missing_answers still asks employee_requested and can stall the receipt. Skip these moves in missing_answers as evaluate does. Test: tests/review/test_core_fix_3.py
## Invariants
1-8: OK
## Disputed tests
none
