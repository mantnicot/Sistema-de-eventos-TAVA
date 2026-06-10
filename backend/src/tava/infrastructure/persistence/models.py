import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from tava.domain.enums import (
    EventStatus,
    PaymentProvider,
    PaymentStatus,
    SeatStatus,
    TicketKind,
    UserRole,
    VenueType,
)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.GENERAL)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    privacy_policy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tickets: Mapped[list["TicketModel"]] = relationship(
        back_populates="owner",
        foreign_keys="TicketModel.owner_id",
    )
    favorites: Mapped[list["FavoriteModel"]] = relationship(back_populates="user")
    collectibles: Mapped[list["CollectibleModel"]] = relationship(back_populates="user")
    reviews: Mapped[list["ReviewModel"]] = relationship(back_populates="user")


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date)
    event_time: Mapped[time] = mapped_column(Time)
    city: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(100))
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.DRAFT)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    main_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trailer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    theatrical_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    organizer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    venue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    gallery: Mapped[list["EventMediaModel"]] = relationship(back_populates="event")
    ticket_types: Mapped[list["TicketTypeModel"]] = relationship(back_populates="event")
    promotions: Mapped[list["PromotionModel"]] = relationship(back_populates="event")


class EventMediaModel(Base):
    __tablename__ = "event_media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    media_type: Mapped[str] = mapped_column(String(20))  # image | video | youtube | vimeo
    url: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    event: Mapped["EventModel"] = relationship(back_populates="gallery")


class VenueModel(Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    venue_type: Mapped[VenueType] = mapped_column(Enum(VenueType))
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)

    sectors: Mapped[list["SectorModel"]] = relationship(back_populates="venue")


class SectorModel(Base):
    __tablename__ = "sectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))  # VIP, Preferencial, General
    color: Mapped[str] = mapped_column(String(20), default="#C9A227")
    price_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.00"))

    venue: Mapped["VenueModel"] = relationship(back_populates="sectors")
    seats: Mapped[list["SeatModel"]] = relationship(back_populates="sector")


class SeatModel(Base):
    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("sector_id", "row_label", "col_label", name="uq_seat_position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"))
    row_label: Mapped[str] = mapped_column(String(10))
    col_label: Mapped[str] = mapped_column(String(10))
    status: Mapped[SeatStatus] = mapped_column(Enum(SeatStatus), default=SeatStatus.AVAILABLE)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)

    sector: Mapped["SectorModel"] = relationship(back_populates="seats")


class TicketTypeModel(Base):
    __tablename__ = "ticket_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[TicketKind] = mapped_column(Enum(TicketKind), default=TicketKind.INDIVIDUAL)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity_available: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    design_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    event: Mapped["EventModel"] = relationship(back_populates="ticket_types")


class PromotionModel(Base):
    __tablename__ = "promotions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    event: Mapped["EventModel"] = relationship(back_populates="promotions")


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    seller_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_provider: Mapped[PaymentProvider | None] = mapped_column(Enum(PaymentProvider), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    wompi_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pending_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    legal_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tickets: Mapped[list["TicketModel"]] = relationship(back_populates="order")


class TicketModel(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"))
    ticket_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ticket_types.id"))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    seat_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("seats.id"), nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    qr_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    ticket_code: Mapped[str | None] = mapped_column(String(12), unique=True, index=True, nullable=True)
    security_hash: Mapped[str] = mapped_column(String(128))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    order: Mapped["OrderModel"] = relationship(back_populates="tickets")
    owner: Mapped["UserModel"] = relationship(
        back_populates="tickets",
        foreign_keys=[owner_id],
    )


class CheckInModel(Base):
    __tablename__ = "check_ins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    validator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    result: Mapped[str] = mapped_column(String(50))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    manual: Mapped[bool] = mapped_column(Boolean, default=False)


class FavoriteModel(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event_favorite"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"))

    user: Mapped["UserModel"] = relationship(back_populates="favorites")


class CollectibleModel(Base):
    __tablename__ = "collectibles"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event_collectible"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    lamina_url: Mapped[str] = mapped_column(String(500))
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="collectibles")


class LoyaltyRewardModel(Base):
    __tablename__ = "loyalty_rewards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    events_required: Mapped[int] = mapped_column(Integer, default=5)
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewModel(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event_review"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="reviews")


class BannerModel(Base):
    __tablename__ = "banners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    image_url: Mapped[str] = mapped_column(String(500))
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_type: Mapped[str] = mapped_column(String(30), default="promocional")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FormFieldModel(Base):
    __tablename__ = "form_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_key: Mapped[str] = mapped_column(String(50), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    field_type: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(200))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailVerificationTokenModel(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SiteSettingModel(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventStaffAssignmentModel(Base):
    __tablename__ = "event_staff_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", "staff_role", name="uq_event_staff_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    staff_role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
