import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token_with_role
from app.db.session import get_db
from app.models.user import User, PasswordReset
from app.schemas.auth import (
    LoginRequest,
    TokenOut,
    UserRegisterRequest,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.services.email_service import EmailService, generate_reset_token, is_valid_email

router = APIRouter(prefix="/auth", tags=["auth"])


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against either PBKDF2 or legacy plaintext value."""
    if "$" not in hashed_password:
        # Legacy fallback to avoid breaking existing rows if any were stored in plaintext.
        return hmac.compare_digest(plain_password, hashed_password)

    try:
        scheme, iterations, salt_b64, digest_b64 = hashed_password.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        computed_digest = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(computed_digest, expected_digest)
    except Exception:
        return False


@router.post("/admin-login", response_model=TokenOut)
def admin_login(payload: LoginRequest):
    settings = get_settings()
    if payload.username != settings.admin_username or payload.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token_with_role(subject=settings.admin_username, role="admin")
    return TokenOut(access_token=token)


@router.post("/user-login", response_model=TokenOut)
def user_login(payload: LoginRequest, db: Session = Depends(get_db)):
    """User login with database lookup"""
    settings = get_settings()

    # Backward-compatible fallback for legacy single user credentials.
    if payload.username == settings.user_username and payload.password == settings.user_password:
        user = db.query(User).filter(User.username == payload.username).first()
        if not user:
            seeded_user = User(
                username=settings.user_username,
                email=f"{settings.user_username}@local.educhat",
                hashed_password=hash_password(settings.user_password),
                full_name="Legacy User",
                is_active=True,
            )
            db.add(seeded_user)
            db.commit()
        token = create_access_token_with_role(subject=settings.user_username, role="user")
        return TokenOut(access_token=token)

    user = db.query(User).filter(User.username == payload.username).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    
    token = create_access_token_with_role(subject=user.username, role="user")
    return TokenOut(access_token=token)


@router.post("/register", response_model=UserResponse)
async def register(
    payload: UserRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register a new user account"""
    
    if not is_valid_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    # Check if username already exists
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Check if email already exists
    existing_email = db.query(User).filter(User.email == payload.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send welcome email in background
    email_service = EmailService()
    if background_tasks is not None:
        background_tasks.add_task(
            email_service.send_welcome_email,
            email=new_user.email,
            username=new_user.username,
        )

    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        full_name=new_user.full_name,
        is_active=new_user.is_active,
        created_at=new_user.created_at.isoformat(),
    )


@router.post("/password-reset-request")
async def request_password_reset(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request password reset - sends email with reset token"""
    
    # Find user by email
    user = db.query(User).filter(User.email == payload.email).first()
    
    if not user:
        # Don't reveal if email exists or not (security best practice)
        return {
            "message": "If an account with this email exists, a password reset link has been sent."
        }

    # Generate reset token
    reset_token = generate_reset_token()
    settings = get_settings()
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )

    # Remove any previous active tokens for this user.
    db.query(PasswordReset).filter(PasswordReset.user_id == user.id).delete()

    # Store reset token in database
    password_reset = PasswordReset(
        user_id=user.id,
        email=user.email,
        token=reset_token,
        expires_at=expires_at,
    )
    
    db.add(password_reset)
    db.commit()

    # Send reset email in background
    email_service = EmailService()
    background_tasks.add_task(
        email_service.send_password_reset_email,
        email=user.email,
        username=user.username,
        reset_token=reset_token,
        reset_url=settings.frontend_password_reset_url,
    )

    return {
        "message": "If an account with this email exists, a password reset link has been sent."
    }


@router.post("/password-reset-confirm", response_model=TokenOut)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Confirm password reset with token and set new password"""
    
    # Find the reset token
    reset_record = (
        db.query(PasswordReset)
        .filter(
            PasswordReset.token == payload.token,
            PasswordReset.email == payload.email,
        )
        .first()
    )

    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check if token has expired
    if reset_record.expires_at < datetime.utcnow():
        db.delete(reset_record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired",
        )

    # Find user and update password
    user = db.query(User).filter(User.id == reset_record.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user.hashed_password = hash_password(payload.new_password)
    user.updated_at = datetime.utcnow()
    
    # Delete the used reset token
    db.delete(reset_record)
    
    db.commit()
    db.refresh(user)

    # Generate new access token and return it
    token = create_access_token_with_role(subject=user.username, role="user")
    return TokenOut(access_token=token)

