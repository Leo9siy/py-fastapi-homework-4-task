from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, status, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_s3_storage_client, get_jwt_auth_manager
from database import get_db, UserModel, UserProfileModel
from exceptions import TokenExpiredError, InvalidTokenError
from schemas.profiles import ProfileResponseSchema, ProfileUpdateSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from storages import S3StorageInterface
from validation import validate_name, validate_gender, validate_birth_date, validate_image


router = APIRouter()


@router.post(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_user_profile(
    user_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    gender: str = Form(...),
    date_of_birth: date = Form(...),
    info: str = Form(...),
    avatar: UploadFile = File(...),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        token_data = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    is_admin = token_data.get("group") == "admin"
    if token_data.get("user_id") != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    user_result = await db.execute(select(UserModel).where(UserModel.id == user_id, UserModel.is_active))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or not active.")

    profile_result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    existing_profile = profile_result.scalar_one_or_none()
    if existing_profile:
        raise HTTPException(status_code=400, detail="User already has a profile.")

    try:
        validate_name(first_name)
        validate_name(last_name)
        validate_gender(gender)
        validate_birth_date(date_of_birth)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not info.strip():
        raise HTTPException(status_code=422, detail="Info field cannot be empty or contain only spaces.")

    try:
        validate_image(avatar)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        avatar_path = await s3_client.upload_avatar(user_id, avatar)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload avatar. Please try again later.")

    profile = UserProfileModel(
        user_id=user_id,
        first_name=first_name.lower(),
        last_name=last_name.lower(),
        gender=gender,
        date_of_birth=date_of_birth,
        info=info,
        avatar=avatar_path
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile


@router.patch(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema
)
async def update_user_profile(
    user_id: int,
    update_data: ProfileUpdateSchema,
    avatar: Optional[UploadFile] = File(None),
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    s3_client: S3StorageInterface = Depends(get_s3_storage_client)
):
    try:
        token_data = jwt_manager.decode_access_token(token)
    except jwt_manager.TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except jwt_manager.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    is_admin = token_data.get("group") == "admin"
    if token_data.get("user_id") != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this profile.")

    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    update_fields = update_data.dict(exclude_unset=True)

    if avatar:
        try:
            validate_image(avatar)
            avatar_path = await s3_client.upload_avatar(user_id, avatar)
            profile.avatar = avatar_path
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload avatar.")

    try:
        if "first_name" in update_fields:
            validate_name(update_fields["first_name"])
        if "last_name" in update_fields:
            validate_name(update_fields["last_name"])
        if "gender" in update_fields:
            validate_gender(update_fields["gender"])
        if "date_of_birth" in update_fields:
            validate_birth_date(update_fields["date_of_birth"])
        if "info" in update_fields and not update_fields["info"].strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


    for key, value in update_fields.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)

    return profile


@router.get(
    "/users/{user_id}/profile/",
    response_model=ProfileResponseSchema
)
async def get_user_profile(
        user_id: int,
        token: str = Depends(get_token),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
):
    try:
        token_data = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    if token_data is None:
        raise HTTPException(status_code=401, detail="Token has expired.")

    is_admin = token_data.get("group") == "admin"

    if token_data.get("user_id") != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="You don't have permission to view this profile.")

    result = await db.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
    profile = result.scalar_one_or_none()

    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return profile
