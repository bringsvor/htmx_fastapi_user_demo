from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    is_active: Optional[bool] = True
    is_verified: Optional[bool] = False
    is_superuser: Optional[bool] = False
    name: Optional[str] = None
    picture: Optional[str] = None


class UserUpdate(BaseModel):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None
    name: Optional[str] = None
    picture: Optional[str] = None