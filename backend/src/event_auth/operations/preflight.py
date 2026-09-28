"""Read-only local readiness checks; never print record contents or secrets."""

import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.session import make_engine
from event_auth.adapters.signing import load_signer
from event_auth.config.settings import load_config
from event_auth.face_lab import model_provenance
from event_auth.operations.recovery import check_data


def inspect() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[4]
    result: dict[str, Any] = {}
    config = load_config(
        Path(os.environ.get("EVENT_AUTH_CONFIG", root / "assets/config/customer_config.json"))
    )
    result["configuration"] = "PASS"
    result["experimental_face"] = config.experimental_face
    model_provenance(root / "assets/models")
    result["model_hashes"] = "PASS"
    if not (root / "frontend/dist/index.html").is_file():
        raise ValueError("Frontend build missing")
    result["frontend_build"] = "PASS"
    vault = Vault.from_file(Path(os.environ["EVENT_AUTH_KEY_FILE"]).expanduser())
    signer = load_signer(Path(os.environ["EVENT_AUTH_SIGNING_KEY_FILE"]).expanduser())
    engine = make_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as db:
            if db.scalar(text("SELECT version_num FROM alembic_version")) != "0004":
                raise ValueError("Expected schema 0004")
            check_data(db, vault, signer)
        result["database_schema"] = "PASS"
        result["encrypted_records_and_coupon_signatures"] = "PASS"
    finally:
        engine.dispose()
    return result


def main() -> None:
    try:
        for name, value in inspect().items():
            print(f"{name}: {value}")
        print(
            "Physical camera, phone trust, timings and dry-run acceptance remain separate checks."
        )
    except Exception:
        raise SystemExit(
            "Preflight failed. Check config, models, build, schema and original keys."
        ) from None


if __name__ == "__main__":
    main()
