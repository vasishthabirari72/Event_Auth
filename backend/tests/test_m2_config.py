import base64
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from event_auth.adapters.crypto import Vault
from event_auth.config.settings import CustomerConfig
from event_auth.core.members.rules import RuleViolation
from event_auth.modules.data_import.reader import read_rows
from pydantic import ValidationError


@pytest.mark.parametrize(
    "change",
    [
        {"primary_color": "#FFFFFF"},
        {"primary_color": "javascript:bad"},
        {"member_fields": [{"key": "name", "label": "Name"}]},
        {"member_fields": [{"key": "a", "label": "A", "type": "select"}]},
        {"consent_version": ""},
        {"default_options": []},
        {"allow_without_consent": True},
    ],
)
def test_invalid_config_fails_closed(change):
    with pytest.raises(ValidationError):
        CustomerConfig(organization="Test Organization", **change)


def test_private_key_file_permissions(tmp_path: Path):
    path = tmp_path / "test.key"
    path.write_bytes(Fernet.generate_key())
    path.chmod(0o644)
    with pytest.raises(ValueError):
        Vault.from_file(path)
    path.chmod(0o600)
    value = Vault.from_file(path)
    assert value.open(value.seal({"test": "value"})) == {"test": "value"}
    link = tmp_path / "alias.key"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        Vault.from_file(link)


@pytest.mark.parametrize(
    "raw",
    [
        b"a,a\n1,2\n",
        b"a,b\n1\n",
        b"a\n=SUM(1)\n",
        b"a\n1\n" + b"2\n" * 1000,
    ],
)
def test_import_file_bounds_and_formula_rejection(raw):
    with pytest.raises(RuleViolation):
        read_rows(base64.b64encode(raw).decode(), "csv")
