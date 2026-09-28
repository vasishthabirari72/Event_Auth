import io
import os
import zipfile

import pytest
from event_auth.adapters.backup import FILES, MAGIC, seal, unseal, write_private
from event_auth.operations.recovery import validate_target

PHRASE = "test-only recovery passphrase"


def bundle():
    return {
        name: (b"Test private payload" if name == "database.dump" else b"test") for name in FILES
    }


def test_authenticated_archive_and_private_exclusive_output(tmp_path):
    first, second = seal(bundle(), PHRASE), seal(bundle(), PHRASE)
    assert first != second and b"Test private payload" not in first
    assert unseal(first, PHRASE) == bundle()
    for value, phrase in [
        (first, "wrong test passphrase"),
        (first[:-1], PHRASE),
        (first[:-1] + bytes([first[-1] ^ 1]), PHRASE),
        (b"invalid" + first, PHRASE),
    ]:
        with pytest.raises(ValueError):
            unseal(value, phrase)
    path = tmp_path / "test.eab"
    write_private(path, first)
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private(path, second)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(FileExistsError):
        write_private(link, second)
    assert path.read_bytes() == first


def test_archive_structure_and_passphrase_rejected():
    with pytest.raises(ValueError):
        seal(bundle(), "short")
    with pytest.raises(ValueError):
        seal({"../storage.key": b"test"}, PHRASE)
    # Even an authenticated archive cannot choose extraction paths.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from event_auth.adapters.backup import derive

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../storage.key", b"test")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + salt + nonce
    malicious = header + AESGCM(derive(PHRASE, salt)).encrypt(nonce, stream.getvalue(), header)
    with pytest.raises(ValueError, match="Unexpected"):
        unseal(malicious, PHRASE)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://event_auth@127.0.0.1:5432/event_auth",
        "postgresql+psycopg://event_auth_restore@127.0.0.1:5432/event_auth_restore",
        "postgresql+psycopg://event_auth_restore@remote:5434/event_auth_restore",
    ],
)
def test_restore_cannot_target_live_or_remote_database(url):
    with pytest.raises(ValueError):
        validate_target(url, "restore-db")
