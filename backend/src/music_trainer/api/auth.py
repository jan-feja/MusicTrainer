"""/api/auth: registering, logging in and out, and managing the account."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from music_trainer.api.dependencies import (
    SESSION_COOKIE,
    AccountsDependency,
    OptionalUser,
    RequiredUser,
    SettingsDependency,
    SongCleanupDependency,
    UserLibraryDependency,
    session_token,
)
from music_trainer.config import Settings
from music_trainer.models import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    User,
)
from music_trainer.services.accounts import UsernameTakenError, WrongPasswordError

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECONDS_PER_DAY = 24 * 60 * 60


@router.get("/me", response_model=User | None)
def me(user: OptionalUser) -> User | None:
    """The logged-in user; null for a guest."""
    return user


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    response: Response,
    accounts: AccountsDependency,
    settings: SettingsDependency,
) -> User:
    """Create an account and log in to it."""
    try:
        user = accounts.register(body.username, body.password)
    except UsernameTakenError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    _log_in(response, accounts.create_session(user.id), settings)
    return user


@router.post("/login", response_model=User)
def login(
    body: LoginRequest,
    response: Response,
    accounts: AccountsDependency,
    settings: SettingsDependency,
) -> User:
    user = accounts.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    _log_in(response, accounts.create_session(user.id), settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, accounts: AccountsDependency, settings: SettingsDependency
) -> Response:
    token = session_token(request)
    if token:
        accounts.end_session(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _log_out(response, settings)
    return response


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: RequiredUser,
    accounts: AccountsDependency,
) -> Response:
    """Set a new password; every other browser logged in to the account is logged out."""
    try:
        accounts.change_password(
            user.id,
            body.current_password,
            body.new_password,
            keep_token=session_token(request) or "",
        )
    except WrongPasswordError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The current password is wrong") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountRequest,
    user: RequiredUser,
    accounts: AccountsDependency,
    user_library: UserLibraryDependency,
    song_cleanup: SongCleanupDependency,
    settings: SettingsDependency,
) -> Response:
    """Delete the account with its library; songs nobody else has are deleted too."""
    video_ids = user_library.video_ids(user.id)
    try:
        accounts.delete_account(user.id, body.password)
    except WrongPasswordError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The password is wrong") from error
    for video_id in video_ids:
        song_cleanup.release(video_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _log_out(response, settings)
    return response


def _log_in(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(settings.session_days * SECONDS_PER_DAY),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


def _log_out(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, samesite="lax", secure=settings.session_cookie_secure
    )
