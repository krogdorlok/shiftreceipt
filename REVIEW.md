VERDICT: FAIL
Milestone: M1   Round: 1   Tests: 2 failed, 105 passed in 0.64s
## Findings
1. [MAJOR] agent.py:65  A malformed resource URI such as `http://[bad` raises ValueError before a valid metadata URL can be tried, so the handler gives a generic error instead of the required schedule fallback. Catch URL parsing errors in `_http` and convert them to DownloadError in `download` at line 37. Test: tests/review/test_m1_1.py
## Invariants
1-8: OK
## Disputed tests
none
