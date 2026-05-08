from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RBACPolicy:
    """Doc-level RBAC. Caller pasa rol → policy decide qué dominios acceder.

    Política simple para el prototipo. Producción: integrar con IdP (Keycloak/Okta).
    """

    @staticmethod
    def can_access(user_role: str, allowed_roles: tuple[str, ...]) -> bool:
        return user_role.lower() in {r.lower() for r in allowed_roles}

    @staticmethod
    def filter_chunks_metadata_value(user_role: str) -> str:
        # CSV stored in Chroma metadata → use $contains on this token
        return user_role.lower()
