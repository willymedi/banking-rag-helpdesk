from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.container import get_settings


def build_limiter() -> Limiter:
    s = get_settings()
    return Limiter(key_func=get_remote_address, default_limits=[f"{s.rate_limit_per_min}/minute"])
