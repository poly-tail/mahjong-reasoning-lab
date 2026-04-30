from __future__ import annotations

from pathlib import Path

import pytest

import naga_ptev.client as client_module
from naga_ptev.client import (
    NagaPtevClient,
    _load_simple_dotenv,
    _load_niconico_credentials_from_keyring,
    _resolve_niconico_credentials,
    _store_niconico_credentials_in_keyring,
)


def test_load_simple_dotenv_parses_basic_key_values(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "# comment",
                "NAGA_NICONICO_MAIL_TEL=test-user",
                'NAGA_NICONICO_PASSWORD="secret-pass"',
            ]
        ),
        encoding="utf-8",
    )

    loaded = _load_simple_dotenv(dotenv_path)

    assert loaded["NAGA_NICONICO_MAIL_TEL"] == "test-user"
    assert loaded["NAGA_NICONICO_PASSWORD"] == "secret-pass"


def test_resolve_niconico_credentials_prefers_env_over_dotenv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "NAGA_NICONICO_MAIL_TEL=dotenv-user",
                "NAGA_NICONICO_PASSWORD=dotenv-pass",
            ]
        ),
        encoding="utf-8",
    )
    storage_path = tmp_path / ".secrets" / "naga_state.json"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NAGA_NICONICO_MAIL_TEL", "env-user")
    monkeypatch.setenv("NAGA_NICONICO_PASSWORD", "env-pass")

    credentials = _resolve_niconico_credentials(storage_path)

    assert credentials == ("env-user", "env-pass")


def test_resolve_niconico_credentials_reads_dotenv_near_storage(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / ".secrets" / "naga_state.json"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "NAGA_NICONICO_MAIL_TEL=dotenv-user",
                "NAGA_NICONICO_PASSWORD=dotenv-pass",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / ".secrets")
    monkeypatch.setattr(client_module, "_keyring", None)

    credentials = _resolve_niconico_credentials(storage_path)

    assert credentials == ("dotenv-user", "dotenv-pass")


class _FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


def test_store_and_load_niconico_credentials_with_keyring(monkeypatch) -> None:
    fake_keyring = _FakeKeyring()
    monkeypatch.setattr(client_module, "_keyring", fake_keyring)

    _store_niconico_credentials_in_keyring("stored-user", "stored-pass")

    assert _load_niconico_credentials_from_keyring() == ("stored-user", "stored-pass")


def test_resolve_niconico_credentials_uses_keyring_before_dotenv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_keyring = _FakeKeyring()
    monkeypatch.setattr(client_module, "_keyring", fake_keyring)
    fake_keyring.set_password(client_module.NAGA_KEYRING_SERVICE, client_module.NAGA_KEYRING_LOGIN_KEY, "keyring-user")
    fake_keyring.set_password(
        client_module.NAGA_KEYRING_SERVICE,
        client_module.NAGA_KEYRING_PASSWORD_KEY,
        "keyring-pass",
    )
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "NAGA_NICONICO_MAIL_TEL=dotenv-user",
                "NAGA_NICONICO_PASSWORD=dotenv-pass",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    credentials = _resolve_niconico_credentials(tmp_path / ".secrets" / "naga_state.json")

    assert credentials == ("keyring-user", "keyring-pass")


@pytest.mark.anyio
async def test_open_with_state_bootstraps_missing_storage(monkeypatch, tmp_path: Path) -> None:
    storage_path = tmp_path / ".secrets" / "naga_state.json"
    client = NagaPtevClient()
    calls: dict[str, object] = {}

    async def fake_bootstrap(target: Path) -> bool:
        calls["target"] = target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
        return True

    monkeypatch.setattr(client, "_bootstrap_storage_state_with_saved_credentials", fake_bootstrap)

    await client.open_with_state(str(storage_path))

    assert calls["target"] == storage_path
    assert storage_path.exists()


@pytest.mark.anyio
async def test_open_with_state_raises_when_bootstrap_missing_and_no_credentials(
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / ".secrets" / "naga_state.json"
    client = NagaPtevClient()

    async def fake_bootstrap(target: Path) -> bool:
        return False

    monkeypatch.setattr(client, "_bootstrap_storage_state_with_saved_credentials", fake_bootstrap)
    monkeypatch.setattr(client_module, "_resolve_niconico_credentials", lambda _path: None)

    with pytest.raises(FileNotFoundError):
        await client.open_with_state(str(storage_path))
