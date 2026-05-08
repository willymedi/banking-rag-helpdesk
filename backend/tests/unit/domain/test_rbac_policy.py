from src.domain.policies.rbac_policy import RBACPolicy


def test_rbac_grants_access_when_role_in_allowed():
    assert RBACPolicy.can_access("dev", ("dev", "auditor")) is True


def test_rbac_denies_when_role_not_in_allowed():
    assert RBACPolicy.can_access("dev", ("security", "compliance")) is False


def test_rbac_case_insensitive():
    assert RBACPolicy.can_access("DEV", ("dev",)) is True
    assert RBACPolicy.can_access("dev", ("DEV",)) is True
