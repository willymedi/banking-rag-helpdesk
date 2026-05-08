from src.domain.policies.confidence_policy import ConfidencePolicy
from src.domain.value_objects.confidence import Confidence


def test_confidence_passes_above_threshold():
    p = ConfidencePolicy(threshold=0.65)
    assert p.is_sufficient(Confidence(0.7), True) is True


def test_confidence_fails_below_threshold():
    p = ConfidencePolicy(threshold=0.65)
    assert p.is_sufficient(Confidence(0.5), True) is False


def test_confidence_fails_when_insufficient_context():
    p = ConfidencePolicy(threshold=0.65)
    assert p.is_sufficient(Confidence(0.99), False) is False


def test_confidence_value_must_be_in_range():
    import pytest

    with pytest.raises(ValueError):
        Confidence(1.5)
    with pytest.raises(ValueError):
        Confidence(-0.1)
