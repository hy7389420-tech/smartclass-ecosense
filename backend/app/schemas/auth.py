from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AccessTokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    id: int
    email: str
    role: str
    student_id: int | None
    is_active: bool


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
