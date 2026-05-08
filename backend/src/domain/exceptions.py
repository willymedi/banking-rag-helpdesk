class DomainError(Exception):
    pass


class InsufficientContextError(DomainError):
    pass


class PromptInjectionDetected(DomainError):
    def __init__(self, attack_type: str, detail: str = "") -> None:
        self.attack_type = attack_type
        self.detail = detail
        super().__init__(f"prompt injection detected: {attack_type} ({detail})")


class CitationMismatchError(DomainError):
    def __init__(self, claim: str) -> None:
        self.claim = claim
        super().__init__(f"claim has no matching citation: {claim[:80]}")


class OutputLeakDetected(DomainError):
    pass


class UnauthorizedRoleError(DomainError):
    pass
