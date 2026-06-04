from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.auth import AuthUseCase
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.services.captcha import verify_captcha
from tava.presentation.api.dependencies import get_current_user
from tava.presentation.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        raise HTTPException(status_code=400, detail="Captcha inválido")
    try:
        uc = AuthUseCase(db)
        user, tokens = await uc.register(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            phone=body.phone,
            document_id=body.document_id,
        )
        return {"user": UserResponse.model_validate(user), "tokens": TokenResponse(**tokens)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    if not await verify_captcha(body.captcha_token):
        raise HTTPException(status_code=400, detail="Captcha inválido")
    try:
        uc = AuthUseCase(db)
        user, tokens = await uc.login(body.email, body.password)
        return {"user": UserResponse.model_validate(user), "tokens": TokenResponse(**tokens)}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    try:
        uc = AuthUseCase(db)
        tokens = await uc.refresh(refresh_token)
        return TokenResponse(**tokens)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return UserResponse.model_validate(user)
