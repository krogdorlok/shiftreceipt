VERDICT: FAIL
Milestone: CORE-FIX   Round: 4   Tests: 1 failed, 98 passed in 0.12s
## Findings
1. [BLOCKER] diff.py:60  Two shifts swapping dates with changed hours evade the exact-shape check and are priced as same-day changes ($90 versus $80 for the two moves). Treat possible same-week cross-day matches with changed hours as needs_review before pricing. Test: tests/review/test_core_fix_6.py
## Invariants
1-8: OK
## Disputed tests
none
