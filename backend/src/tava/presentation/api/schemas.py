from datetime import date, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from tava.domain.enums import EventStatus, TicketKind, UserRole, VenueType


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str | None = Field(default=None, min_length=8, max_length=128)
    password_encrypted: str | None = None
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = None
    document_id: str | None = None
    captcha_token: str | None = None

    @model_validator(mode="after")
    def require_password(self):
        if not self.password and not self.password_encrypted:
            raise ValueError("Se requiere contraseña o password_encrypted")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str | None = None
    password_encrypted: str | None = None
    captcha_token: str | None = None

    @model_validator(mode="after")
    def require_password(self):
        if not self.password and not self.password_encrypted:
            raise ValueError("Se requiere contraseña o password_encrypted")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    phone: str | None = None

    class Config:
        from_attributes = True


class EventCreateRequest(BaseModel):
    name: str
    description: str
    event_date: date
    event_time: time
    city: str
    address: str
    category: str
    capacity: int = 0
    status: EventStatus = EventStatus.DRAFT
    main_image_url: str | None = None
    trailer_url: str | None = None
    venue_id: UUID | None = None


class EventResponse(BaseModel):
    id: UUID
    name: str
    description: str
    event_date: date
    event_time: time
    city: str
    address: str
    category: str
    status: EventStatus
    capacity: int
    main_image_url: str | None = None
    trailer_url: str | None = None


class VenueCreateRequest(BaseModel):
    name: str
    venue_type: VenueType
    capacity: int = 0
    address: str | None = None


class SectorCreateRequest(BaseModel):
    name: str
    color: str = "#C9A227"
    price_multiplier: Decimal = Decimal("1.00")
    rows: int = Field(ge=1, le=100)
    cols: int = Field(ge=1, le=100)


class TicketTypeCreateRequest(BaseModel):
    event_id: UUID
    name: str
    kind: TicketKind = TicketKind.INDIVIDUAL
    price: Decimal
    quantity_available: int
    benefits: str | None = None


class ValidateQrRequest(BaseModel):
    qr_token: str


class ValidationResponse(BaseModel):
    result: str
    ticket_id: UUID | None = None
    message: str


class PurchaseRequest(BaseModel):
    event_id: UUID
    ticket_type_id: UUID
    quantity: int = Field(ge=1, le=20)
    seat_ids: list[UUID] | None = None
    legal_accepted: bool = False
    captcha_token: str | None = None
    promotion_code: str | None = None


class ApiMessage(BaseModel):
    message: str
    success: bool = True
