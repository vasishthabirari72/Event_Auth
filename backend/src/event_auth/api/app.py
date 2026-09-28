import os
from collections.abc import Callable
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware

from event_auth.adapters.crypto import Vault
from event_auth.adapters.database.session import make_engine
from event_auth.adapters.face.sface import CaptureRejected
from event_auth.adapters.pdf import PdfOutput
from event_auth.adapters.signing import load_signer
from event_auth.api.admin_routes import router
from event_auth.api.checkin_routes import router as checkin_router
from event_auth.api.counter_routes import router as counter_router
from event_auth.config.settings import CustomerConfig, load_config
from event_auth.core.documents import DocumentOutput
from event_auth.core.members.rules import RuleViolation
from event_auth.services.enrollment import Enrollment, capture_error


def database_ready() -> bool:
    url = os.environ.get("DATABASE_URL")
    if not url:
        return False
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        # Connection exceptions can include credentials; return only a status.
        return False
    finally:
        engine.dispose()


def create_app(
    readiness: Callable[[], bool] = database_ready,
    frontend: Path | None = None,
    sessions: sessionmaker[Session] | None = None,
    vault: Vault | None = None,
    config: CustomerConfig | None = None,
    enrollment: Enrollment | None = None,
    signer: Ed25519PrivateKey | None = None,
    document_output: DocumentOutput | None = None,
) -> FastAPI:
    app = FastAPI(title="Event Auth", docs_url=None, redoc_url=None, openapi_url=None)
    root = Path(__file__).resolve().parents[4]
    app.state.config = config or load_config(
        Path(os.environ.get("EVENT_AUTH_CONFIG", str(root / "assets/config/customer_config.json")))
    )
    app.state.secure_cookie = os.environ.get("EVENT_AUTH_COOKIE_SECURE", "true") != "false"
    if (
        sessions is None
        and os.environ.get("DATABASE_URL")
        and os.environ.get("EVENT_AUTH_KEY_FILE")
    ):
        sessions = sessionmaker(make_engine(os.environ["DATABASE_URL"]), expire_on_commit=False)
        vault = Vault.from_file(Path(os.environ["EVENT_AUTH_KEY_FILE"]).expanduser())
    if sessions is not None:
        if vault is None:
            raise ValueError("Encrypted storage requires a key")
        from sqlalchemy import select

        from event_auth.adapters.database.models import Member

        with sessions() as db:
            sample = db.scalar(select(Member).limit(1))
            if sample is not None:
                vault.open(sample.personal)  # Fail startup with the wrong recovery key.
    app.state.sessions, app.state.vault = sessions, vault
    app.state.enrollment = enrollment or Enrollment(root / "assets/models")
    key_path = os.environ.get("EVENT_AUTH_SIGNING_KEY_FILE")
    app.state.signer = signer or (load_signer(Path(key_path).expanduser()) if key_path else None)
    app.state.document_output = document_output or PdfOutput()
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.environ.get("EVENT_AUTH_HOSTS", "127.0.0.1,localhost,testserver").split(
            ","
        ),
    )
    origins = set(
        os.environ.get(
            "EVENT_AUTH_ORIGINS",
            "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173,http://testserver",
        ).split(",")
    )

    @app.middleware("http")
    async def protect(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not app.state.secure_cookie and request.url.hostname not in {
            "127.0.0.1",
            "localhost",
            "testserver",
        }:
            return JSONResponse({"detail": "https_required"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("Origin") not in origins:
                return JSONResponse({"detail": "invalid_origin"}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 7_000_000:
                    return JSONResponse({"detail": "request_too_large"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse({"detail": "invalid_request"}, status_code=422)

    @app.exception_handler(RuleViolation)
    async def rule_error(request: Request, error: RuleViolation) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(CaptureRejected)
    async def face_error(request: Request, error: CaptureRejected) -> JSONResponse:
        return JSONResponse({"detail": capture_error(error)}, status_code=422)

    @app.exception_handler(PermissionError)
    async def permission_error(request: Request, error: PermissionError) -> JSONResponse:
        return JSONResponse({"detail": "forbidden"}, status_code=403)

    @app.exception_handler(LookupError)
    async def missing_error(request: Request, error: LookupError) -> JSONResponse:
        return JSONResponse({"detail": "not_found"}, status_code=404)

    @app.exception_handler(IntegrityError)
    async def conflict_error(request: Request, error: IntegrityError) -> JSONResponse:
        return JSONResponse({"detail": "duplicate_or_in_use"}, status_code=409)

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse({"detail": "storage_unavailable"}, status_code=503)

    app.include_router(router)
    app.include_router(checkin_router)
    app.include_router(counter_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/ready")
    def ready() -> JSONResponse:
        available = readiness()
        return JSONResponse(
            {"status": "ready" if available else "unavailable"},
            status_code=200 if available else 503,
        )

    built = frontend or Path(__file__).resolve().parents[4] / "frontend" / "dist"
    if built.is_dir():
        app.mount("/", StaticFiles(directory=built, html=True), name="frontend")
    return app


app = create_app()
