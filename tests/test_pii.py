from copilot.guardrails.pii import has_pii, redact


def test_redacts_email():
    out = redact("contact me at luciano@example.com please")
    assert "luciano@example.com" not in out
    assert "[EMAIL]" in out


def test_redacts_card_like_number():
    out = redact("card 4111 1111 1111 1111")
    assert "4111" not in out
    assert "[CARD]" in out


def test_clean_text_unchanged():
    text = "NYC to London business class thursday"
    assert redact(text) == text
    assert not has_pii(text)
