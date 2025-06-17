from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator

from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)


class ProfileCreateSchema(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str

    @field_validator("first_name", "last_name")
    @classmethod
    def name_validator(cls, v):
        return validate_name(v)

    @field_validator("gender")
    @classmethod
    def gender_validator(cls, v):
        return validate_gender(v)

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_validator(cls, v):
        return validate_birth_date(v)

    @field_validator("info")
    @classmethod
    def info_validator(cls, v):
        if not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    class Config:
        from_attributes = True


class ProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def name_validator(cls, v):
        return validate_name(v)

    @field_validator("gender")
    @classmethod
    def gender_validator(cls, v):
        return validate_gender(v)

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_validator(cls, v):
        return validate_birth_date(v)

    @field_validator("info")
    @classmethod
    def info_validator(cls, v):
        if not v.strip():
            raise ValueError("Info field cannot be empty.")
        return v
