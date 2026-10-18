"""Invariant 3 applies to manager estimates as well as worker receipts."""
import re

from conftest import fixture
from extract import schedule_text
from test_flow import A, say  # noqa: F401


def test_manager_does_not_price_change_without_cover_or_change_answers(A):
    say(A, "manager", "MODE manager")
    say(A, "manager", "RATE 20")
    say(A, "manager", schedule_text(fixture("v1")))
    response = say(A, "manager", schedule_text(fixture("v2")))

    assert not re.search(r"would cost about \$[\d,.]+", response)
