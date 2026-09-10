from typing import Literal

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
    requested_plan: Literal["trial", "pro", "business"] = "trial"
    active_channel: Literal["start", "wb"] = "start"
    marketplace_interest: Literal["ozon", "yandex", "kaspi", "uzum"] | None = None
    requested_stores: Literal[1, 3, 10] = 1
    requested_modules: list[Literal["cards", "profit", "director", "fbo"]] = Field(default_factory=list, max_length=4)

    @field_validator("requested_modules")
    @classmethod
    def unique_modules(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Выбранные модули не должны повторяться")
        return value


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
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_challenge_token: str | None = None
    next_path: str | None = None


class MfaPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class MfaLoginRequest(MfaCodeRequest):
    challenge_token: str = Field(min_length=20, max_length=512)


class MfaDisableRequest(MfaCodeRequest, MfaPasswordRequest):
    pass


class StepUpRequest(MfaPasswordRequest):
    code: str = Field(default="", max_length=32)


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
