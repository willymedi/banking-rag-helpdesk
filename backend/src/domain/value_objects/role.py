from enum import Enum


class UserRole(str, Enum):
    DEV = "dev"
    ARCHITECT = "architect"
    SECURITY = "security"
    SRE = "sre"
    AUDITOR = "auditor"
    COMPLIANCE = "compliance"

    @classmethod
    def from_str(cls, value: str) -> "UserRole":
        try:
            return cls(value.lower())
        except ValueError as exc:
            raise ValueError(f"unknown role: {value}") from exc
