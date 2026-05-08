from src.application.security.pii_redactor import PIIRedactor


def test_redacts_email_via_regex_fallback():
    r = PIIRedactor(use_presidio=False)
    out = r.redact("Contactá a juan.perez@banco.com.co para más info")
    assert "juan.perez@banco.com.co" not in out.text
    assert "[PII_EMAIL]" in out.text
    assert "EMAIL" in out.found


def test_redacts_credit_card():
    r = PIIRedactor(use_presidio=False)
    out = r.redact("Mi tarjeta es 4111-1111-1111-1111 y la usé ayer")
    assert "4111" not in out.text
    assert "[PII_CREDIT_CARD]" in out.text


def test_redacts_ip():
    r = PIIRedactor(use_presidio=False)
    out = r.redact("Server crashed at 192.168.1.42")
    assert "192.168.1.42" not in out.text
    assert "[PII_IP]" in out.text


def test_no_pii_no_change():
    r = PIIRedactor(use_presidio=False)
    text = "¿Qué es un microservicio?"
    out = r.redact(text)
    assert out.text == text
    assert out.found == ()
