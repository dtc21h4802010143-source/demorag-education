from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str | None = Field(default=None, max_length=255)

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "secure_pass123",
                "full_name": "John Doe"
            }
        }


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class PasswordResetRequest(BaseModel):
    email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com"
            }
        }


class PasswordResetConfirm(BaseModel):
    token: str
    email: EmailStr
    new_password: str = Field(..., min_length=6, max_length=100)

    class Config:
        json_schema_extra = {
            "example": {
                "token": "reset_token_here",
                "email": "john@example.com",
                "new_password": "new_secure_pass123"
            }
        }

