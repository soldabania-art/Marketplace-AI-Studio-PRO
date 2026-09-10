from pydantic import BaseModel, EmailStr, Field, field_validator


class StrongPasswordModel(BaseModel):
    @field_validator("password", "new_password", check_fields=False)
    @classmethod
    def strong_password(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("Пароль должен содержать не менее 12 символов")
        classes = sum((any(char.islower() for char in value), any(char.isupper() for char in value),
                       any(char.isdigit() for char in value), any(not char.isalnum() for char in value)))
        if classes < 3:
            raise ValueError("Используйте минимум три типа символов: строчные, заглавные, цифры или специальные знаки")
        return value


class RegisterRequest(StrongPasswordModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(default="", max_length=160)
    workspace_name: str = Field(default="Мой магазин", min_length=2, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenActionRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class PasswordResetConfirmRequest(TokenActionRequest, StrongPasswordModel):
    new_password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    email_verified: bool
    workspace_id: str
    workspace_name: str
    role: str
    plan_code: str
    subscription_status: str
    is_platform_admin: bool = False
