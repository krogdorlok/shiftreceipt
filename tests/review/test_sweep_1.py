from parser import parse


def test_negated_send_prose_does_not_authorize_email():
    assert parse("Do not send receipt 7 to my manager.") is None
