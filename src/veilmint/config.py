"""Explicit local settings. Secrets are never included in representations."""

from dataclasses import dataclass, field
import os
import re
from pathlib import Path

from .runtime.api import RuntimeMode


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path("data/synthetic-demo.sqlite3")
    mode: RuntimeMode = RuntimeMode.OBSERVE
    hmac_key: bytes | None = field(default=None, repr=False)
    operator_token: str | None = field(default=None, repr=False)
    bank_mode: RuntimeMode = RuntimeMode.ENFORCE
    bank_secure_cookie: bool = False
    response_inspection_demo: bool = False

    def __post_init__(self):
        object.__setattr__(self, "database_path", Path(self.database_path))
        try:
            object.__setattr__(self, "mode", RuntimeMode(self.mode))
            object.__setattr__(self, "bank_mode", RuntimeMode(self.bank_mode))
        except ValueError:
            raise ValueError("VEILMINT_MODE must be OBSERVE, WARN or ENFORCE") from None
        if self.hmac_key is not None and (not isinstance(self.hmac_key, bytes) or len(self.hmac_key) < 32):
            raise ValueError("HMAC configuration must contain at least 32 bytes")
        if self.operator_token is not None and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',self.operator_token) is None:
            raise ValueError('Operator proxy token must be 32–128 URL-safe characters')

    @classmethod
    def from_env(cls):
        key = os.environ.get("VEILMINT_HMAC_KEY")
        return cls(
            database_path=Path(os.environ.get("VEILMINT_DB", "data/synthetic-demo.sqlite3")),
            mode=os.environ.get("VEILMINT_MODE", "OBSERVE"),
            hmac_key=key.encode("utf-8") if key else None,
            operator_token=os.environ.get('VEILMINT_OPERATOR_TOKEN') or None,
            bank_mode=os.environ.get('NEXUS_MODE','ENFORCE'),
            bank_secure_cookie=os.environ.get('NEXUS_SECURE_COOKIE','false').lower()=='true',
            response_inspection_demo=os.environ.get('VEILMINT_RESPONSE_INSPECTION_DEMO','false').lower()=='true',
        )
