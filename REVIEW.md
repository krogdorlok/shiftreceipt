VERDICT: FAIL
Milestone: M1   Round: 2   Tests: 2 failed, 107 passed in 0.62s
## Findings
1. [MAJOR] agent.py:57  A 200 image/png response with zero bytes returns success, so the handler claims it received a 1 KB schedule instead of offering the typed fallback. Raise DownloadError when the body is empty. Test: tests/review/test_m1_2.py
2. [MAJOR] agent.py:41  HTTPX reads redirect bodies before the 10 MB cap runs; an 11 MB redirect body is accepted and larger ones can exhaust memory. Follow redirects while streaming and cap each response body. Test: tests/review/test_m1_2.py
## Invariants
1-8: OK
## Disputed tests
none
