from datetime import timedelta

import orjson
from fastapi import Depends, FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from .config import get_settings
from .middleware import (
    AuditMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    cors_options,
)
from starlette.middleware.cors import CORSMiddleware
from .security import create_access_token, get_current_user
from .fhir.endpoints import router as fhir_router


def orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()


app = FastAPI(
    title="NAMASTE FHIR Terminology Service", default_response_class=ORJSONResponse
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(CORSMiddleware, **cors_options())

app.include_router(fhir_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/auth/token")
async def auth_token(form_data: OAuth2PasswordRequestForm = Depends()):
    sub = form_data.username or "anonymous"
    expires_minutes = get_settings().access_token_expire_minutes
    expires_delta = timedelta(minutes=expires_minutes)
    token = create_access_token(
        subject=sub,
        scopes=form_data.scopes,
        expires_delta=expires_delta,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": int(expires_delta.total_seconds()),
    }


@app.get("/me")
async def me(user=Depends(get_current_user)):
    return user
