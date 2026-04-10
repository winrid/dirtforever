from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


PBKDF2_ROUNDS = 120_000


@dataclass
class Account:
    username: str
    email: str
    password_hash: str
    salt: str
    profile: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "salt": self.salt,
            "profile": self.profile,
        }


class AccountStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create_account(self, username: str, password: str, email: str = "") -> Account:
        normalized = self._normalize_username(username)
        path = self._path_for(normalized)
        if path.exists():
            raise ValueError(f"account already exists: {normalized}")

        salt_bytes = secrets.token_bytes(16)
        password_hash = self._hash_password(password, salt_bytes)
        account = Account(
            username=normalized,
            email=email.strip(),
            password_hash=password_hash,
            salt=base64.b64encode(salt_bytes).decode("ascii"),
            profile={
                "display_name": normalized,
                "created_at_epoch": int(time.time()),
                "wallet": {"credits": 0},
                "flags": {"accepted_terms": False},
            },
        )
        self._write_account(path, account)
        return account

    def authenticate(self, username: str, password: str) -> Optional[Account]:
        account = self.get_account(username)
        if not account:
            return None

        salt = base64.b64decode(account.salt.encode("ascii"))
        expected = self._hash_password(password, salt)
        if not hmac.compare_digest(expected, account.password_hash):
            return None
        return account

    def get_account(self, username: str) -> Optional[Account]:
        normalized = self._normalize_username(username)
        path = self._path_for(normalized)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Account(
            username=raw["username"],
            email=raw.get("email", ""),
            password_hash=raw["password_hash"],
            salt=raw["salt"],
            profile=raw.get("profile", {}),
        )

    def mark_terms_accepted(self, username: str) -> Account:
        account = self._require_account(username)
        account.profile.setdefault("flags", {})["accepted_terms"] = True
        self._write_account(self._path_for(account.username), account)
        return account

    def _require_account(self, username: str) -> Account:
        account = self.get_account(username)
        if not account:
            raise ValueError(f"unknown account: {username}")
        return account

    def _write_account(self, path: Path, account: Account) -> None:
        path.write_text(json.dumps(account.to_dict(), indent=2), encoding="utf-8")

    def _path_for(self, username: str) -> Path:
        safe_name = "".join(ch for ch in username if ch.isalnum() or ch in {"_", "-"})
        if not safe_name:
            raise ValueError("username must contain at least one safe character")
        return self.root / f"{safe_name}.json"

    @staticmethod
    def _normalize_username(username: str) -> str:
        value = username.strip().lower()
        if not value:
            raise ValueError("username is required")
        return value

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PBKDF2_ROUNDS,
        )
        return base64.b64encode(digest).decode("ascii")
