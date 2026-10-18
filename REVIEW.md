VERDICT: FAIL
Milestone: CORE-FIX   Round: 3   Tests: 1 failed, 97 passed in 0.13s
## Findings
1. [BLOCKER] diff.py:52  When one of two Monday shifts moves to Tuesday, Monday is marked needs_review but Tuesday is paid as a new shift ($20 in the test); the actual date and location move would be $40. Carry unmatched shifts from multi-shift days into same-week ambiguity detection and mark the possible counterpart needs_review. Test: tests/review/test_core_fix_5.py
## Invariants
1-8: OK
## Disputed tests
none
