VERDICT: FAIL
Milestone: M2   Round: 1   Tests: 3 failed, 126 passed in 0.81s
## Findings
1. [MAJOR] extract.py:103  Empty Gemini shifts return no warning, so a non-schedule image prints a bare SCHEDULE block instead of the required unreadable fallback. Return ([], ["unreadable"]) when no rows are extracted. Test: tests/review/test_m2_1.py
2. [MAJOR] extract.py:37  Missing ambiguous defaults to False, accepting a row without the required uncertainty flag as a definite shift. Require the field so malformed output falls back as unreadable. Test: tests/review/test_m2_2.py
3. [MAJOR] extract.py:53  The interactions request omits response_mime_type, which the installed SDK requires with response_format; the TypeError fallback can fail instead of extracting shifts. Pass response_mime_type="application/json" alongside the schema. Test: tests/review/test_m2_3.py
## Invariants
1-8: OK
## Disputed tests
none
