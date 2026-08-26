from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ProviderCredential:
    provider: str
    key_name: str
    source: str = "keychain"
    metadata: dict[str, Any] | None = None


class CredentialManager:
    """
    Secure provider credential manager.

    Priority:
        1. macOS Keychain
        2. environment variables
        3. explicitly supplied runtime credentials

    Secrets are never written to project manifests or provider catalog files.
    """

    SERVICE_PREFIX = "AI-Movie-Studio/provider"

    def __init__(self, app_name: str = "AI Movie Studio"):
        self.app_name = app_name

    def _service(self, provider: str) -> str:
        return f"{self.SERVICE_PREFIX}/{provider}"

    def set_key(self, provider: str, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")

        api_key = api_key.strip()

        if self._is_macos():
            self._keychain_set(self._service(provider), api_key)
            return

        raise RuntimeError(
            "Secure credential storage is currently supported on macOS."
        )

    def get_key(self, provider: str) -> str | None:
        if self._is_macos():
            value = self._keychain_get(self._service(provider))
            if value:
                return value

        env_name = self._environment_name(provider)
        return os.environ.get(env_name)

    def delete_key(self, provider: str) -> None:
        if self._is_macos():
            self._keychain_delete(self._service(provider))

    def has_key(self, provider: str) -> bool:
        return bool(self.get_key(provider))

    def list_configured(self, providers: list[str]) -> list[str]:
        return [
            provider
            for provider in providers
            if self.has_key(provider)
        ]

    @staticmethod
    def _environment_name(provider: str) -> str:
        normalized = "".join(
            char if char.isalnum() else "_"
            for char in provider.upper()
        )
        return f"{normalized}_API_KEY"

    @staticmethod
    def _is_macos() -> bool:
        return os.uname().sysname == "Darwin"

    @staticmethod
    def _keychain_set(service: str, value: str) -> None:
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-a",
                "ai-movie-studio",
                "-s",
                service,
                "-w",
                value,
                "-U",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    @staticmethod
    def _keychain_get(service: str) -> str | None:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                "ai-movie-studio",
                "-s",
                service,
                "-w",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        if result.returncode != 0:
            return None

        value = result.stdout.strip()
        return value or None

    @staticmethod
    def _keychain_delete(service: str) -> None:
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-a",
                "ai-movie-studio",
                "-s",
                service,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
