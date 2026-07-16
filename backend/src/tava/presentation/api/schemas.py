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
    phone: str = Field(min_length=7, max_length=30, pattern=r"^[\d\s+\-()]{7,30}$")
    document_id: str | None = None
    captcha_token: str | None = None
    accept_privacy_policy: bool = False
    accept_marketing: bool = False

    @model_validator(mode="after")
    def require_password(self):
        if not self.password and not self.password_encrypted:
            raise ValueError("Se requiere contraseña o password_encrypted")
        if not self.accept_privacy_policy:
            raise ValueError(
                "Debe aceptar el tratamiento de datos personales y los términos de la plataforma TAVA"
            )
        return self


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    captcha_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    password_encrypted: str | None = None
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
    email_verified: bool = False

    class Config:
        from_attributes = True


class UserAdminResponse(UserResponse):
    is_active: bool = True


class CastMemberSchema(BaseModel):
    name: str
    photo_url: str | None = None
    role: str | None = None


class SeatingBlockSchema(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    rows: int = Field(ge=1, le=30)
    cols: int = Field(ge=1, le=30)
    row_labels: list[str] | None = None
    col_labels: list[str] | None = None
    ticket_type_id: str | None = None


class SeatingConfigSchema(BaseModel):
    enabled: bool = False
    stage_label: str = "Escenario"
    blocks: list[SeatingBlockSchema] = Field(default_factory=list)
    seat_ticket_types: dict[str, str] | None = None


class TheatricalDetailsSchema(BaseModel):
    synopsis: str | None = None
    cast: list[str] = Field(default_factory=list)
    cast_members: list[CastMemberSchema] = Field(default_factory=list)
    director: str | None = None
    duration_minutes: int | None = None
    age_rating: str | None = None
    language: str | None = None
    warnings: str | None = None
    credits: str | None = None
    seating: SeatingConfigSchema | None = None
    sale_mode: str | None = Field(default=None, pattern="^(system|whatsapp)$")
    whatsapp_number: str | None = Field(default=None, max_length=40)
    whatsapp_message: str | None = Field(default=None, max_length=500)


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse
    email_sent: bool = True


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
    theatrical_details: TheatricalDetailsSchema | None = None


class EventMediaResponse(BaseModel):
    id: UUID
    media_type: str
    url: str
    sort_order: int


class EventMediaCreateRequest(BaseModel):
    media_type: str = Field(pattern="^(image|video|youtube|vimeo)$")
    url: str = Field(max_length=500)
    sort_order: int = 0


class TicketTypePublicResponse(BaseModel):
    id: UUID
    name: str
    kind: TicketKind
    price: Decimal
    quantity_available: int
    benefits: str | None = None


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
    theatrical_details: TheatricalDetailsSchema | None = None
    tickets_available: int = 0


class EventDetailResponse(EventResponse):
    gallery: list[EventMediaResponse] = Field(default_factory=list)
    ticket_types: list[TicketTypePublicResponse] = Field(default_factory=list)
    seating_enabled: bool = False


class SeatingSyncRequest(BaseModel):
    seating: SeatingConfigSchema


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


class TicketTypeUpsertItem(BaseModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    kind: TicketKind = TicketKind.INDIVIDUAL
    price: Decimal = Field(ge=0)
    quantity_available: int = Field(ge=0)
    benefits: str | None = None


class TicketTypesSyncRequest(BaseModel):
    ticket_types: list[TicketTypeUpsertItem] = Field(default_factory=list)


class EventStaffUpdateRequest(BaseModel):
    validator_ids: list[UUID] = Field(default_factory=list)
    seller_ids: list[UUID] = Field(default_factory=list)


class EventStaffResponse(BaseModel):
    validator_ids: list[UUID]
    seller_ids: list[UUID]


class ValidateQrRequest(BaseModel):
    qr_token: str


class ValidationResponse(BaseModel):
    result: str
    ticket_id: UUID | None = None
    message: str
    holder_name: str | None = None
    event_id: UUID | None = None
    event_name: str | None = None
    ingresados: int | None = None
    boletas_vendidas: int | None = None
    pendientes_ingreso: int | None = None


class AttendeeItem(BaseModel):
    ticket_id: UUID
    holder_name: str | None = None
    ticket_code: str | None = None
    is_used: bool
    is_cancelled: bool = False
    used_at: str | None = None


class BroadcastEmailRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=4000)


class CancelTicketRequest(BaseModel):
    notify_holder: bool = True


class ClaimTicketsRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class AdminIssueTicketsRequest(BaseModel):
    event_id: UUID
    ticket_type_id: UUID
    quantity: int = Field(ge=1, le=20)
    buyer_name: str = Field(min_length=2, max_length=200)
    buyer_email: EmailStr
    holder_names: list[str] | None = None


class AttendeesListResponse(BaseModel):
    event_id: UUID
    event_name: str
    ingresados: int
    boletas_vendidas: int
    pendientes_ingreso: int
    attendees: list[AttendeeItem]


class PurchaseRequest(BaseModel):
    event_id: UUID
    ticket_type_id: UUID
    quantity: int = Field(ge=1, le=20)
    holder_names: list[str] | None = None
    seat_ids: list[UUID] | None = None
    legal_accepted: bool = False
    captcha_token: str | None = None
    promotion_code: str | None = None


class SellTicketRequest(BaseModel):
    event_id: UUID
    ticket_type_id: UUID
    quantity: int = Field(ge=1, le=20)
    buyer_email: EmailStr
    holder_names: list[str] = Field(min_length=1)
    legal_accepted: bool = True
    captcha_token: str | None = None

    @model_validator(mode="after")
    def holders_match_qty(self):
        if len(self.holder_names) == 1:
            return self
        if len(self.holder_names) != self.quantity:
            raise ValueError("Debe indicar un nombre por cada boleta (holder_names)")
        return self


class ApiMessage(BaseModel):
    message: str
    success: bool = True
