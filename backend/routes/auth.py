"""CampusFix account registration and bearer-token authentication."""

import os
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints
from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert

from backend.models.user import User

TOKEN_ISSUER = "campusfix"
TOKEN_AUDIENCE = "campusfix-client"
TOKEN_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(minutes=30)
BEARER = HTTPBearer(auto_error=False)
PUBLIC_COLUMNS = (User.id, User.name, User.email, User.role)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=8, max_length=128)]


class RegisterInput(LoginInput):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class PublicUser(BaseModel):
    id: int
    name: str
    email: str
    role: Literal["Student", "Staff", "Admin"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: PublicUser


class PrivateInputRoute(APIRoute):
    """Keep rejected credential values out of validation responses."""

    def get_route_handler(self):
        handle = super().get_route_handler()

        async def handle_without_input(request: Request):
            try:
                return await handle(request)
            except RequestValidationError as exc:
                fields = [
                    {"loc": error["loc"], "type": error["type"]}
                    for error in exc.errors()
                ]
                return JSONResponse(status_code=422, content={"detail": fields})

        return handle_without_input


def unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthRoutes:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.signing_key = os.environ.get("CAMPUSFIX_AUTH_SECRET", "")
        if len(self.signing_key.encode()) < 32:
            raise RuntimeError("Run python -m backend.setup_auth_key and start Uvicorn with --env-file .env.")
        self.passwords = PasswordHash.recommended()
        self.dummy_hash = self.passwords.hash(token_urlsafe(32))

        self.router = APIRouter(prefix="/api/auth", tags=["Authentication"], route_class=PrivateInputRoute)
        self.router.add_api_route(
            "/register", self.register, methods=["POST"], status_code=201, response_model=PublicUser
        )
        self.router.add_api_route(
            "/login", self.login, methods=["POST"], response_model=LoginResponse
        )
        self.router.add_api_route(
            "/me", self.current_user, methods=["GET"], response_model=PublicUser
        )

    def register(self, body: RegisterInput) -> PublicUser:
        values = {
            "name": body.name,
            "email": str(body.email).lower(),
            "password_hash": self.passwords.hash(body.password.get_secret_value()),
            "role": "Student",
        }
        statement = (
            insert(User)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(*PUBLIC_COLUMNS)
        )
        with self.engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=409, detail="An account with that email already exists.")
        return PublicUser.model_validate(row)

    def login(self, body: LoginInput, response: Response) -> LoginResponse:
        query = select(*PUBLIC_COLUMNS, User.password_hash).where(User.email == str(body.email).lower())
        with self.engine.connect() as connection:
            row = connection.execute(query).mappings().one_or_none()

        stored_hash = row["password_hash"] if row is not None else self.dummy_hash
        try:
            valid = self.passwords.verify(body.password.get_secret_value(), stored_hash)
        except (UnknownHashError, ValueError):
            valid = False
        if row is None or not valid:
            raise unauthorized("Invalid email or password.")

        user = PublicUser.model_validate(row)
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user.id), "iss": TOKEN_ISSUER, "aud": TOKEN_AUDIENCE,
                "iat": now, "exp": now + TOKEN_TTL,
            },
            self.signing_key,
            algorithm=TOKEN_ALGORITHM,
        )
        response.headers["Cache-Control"] = "no-store"
        return LoginResponse(access_token=token, expires_in=int(TOKEN_TTL.total_seconds()), user=user)

    def current_user(
        self, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)]
    ) -> PublicUser:
        if credentials is None:
            raise unauthorized("Sign in to continue.")

        try:
            claims = jwt.decode(
                credentials.credentials, self.signing_key,
                algorithms=[TOKEN_ALGORITHM], issuer=TOKEN_ISSUER, audience=TOKEN_AUDIENCE,
                options={"require": ["sub", "iss", "aud", "iat", "exp"]},
            )
            user_id = int(claims["sub"])
            if not 0 < user_id <= 2_147_483_647:
                raise ValueError("User ID outside the PostgreSQL integer range")
        except (jwt.InvalidTokenError, ValueError):
            raise unauthorized("Invalid or expired access token.") from None

        with self.engine.connect() as connection:
            row = connection.execute(
                select(*PUBLIC_COLUMNS).where(User.id == user_id)
            ).mappings().one_or_none()
        if row is None:
            raise unauthorized("Invalid or expired access token.")
        return PublicUser.model_validate(row)
