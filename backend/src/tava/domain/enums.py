import enum


class UserRole(str, enum.Enum):
    GENERAL = "general"
    ADMIN = "admin"
    VALIDATOR = "validator"
    SELLER = "seller"


class EventStatus(str, enum.Enum):
    DRAFT = "borrador"
    SCHEDULED = "programado"
    PUBLISHED = "publicado"
    SOLD_OUT = "agotado"
    IN_PROGRESS = "en_curso"
    FINISHED = "finalizado"
    CANCELLED = "cancelado"


class VenueType(str, enum.Enum):
    THEATER = "teatro"
    AUDITORIUM = "auditorio"
    OPEN_SPACE = "espacio_abierto"
    BAR_CAFE = "bar_cafeteria"


class SeatStatus(str, enum.Enum):
    AVAILABLE = "disponible"
    RESERVED = "reservada"
    SOLD = "vendida"
    BLOCKED = "bloqueada"


class TicketKind(str, enum.Enum):
    INDIVIDUAL = "individual"
    GROUP = "grupal"
    VIP = "vip"
    PROMOTIONAL = "promocional"
    COURTESY = "cortesia"


class PaymentStatus(str, enum.Enum):
    PENDING = "pendiente"
    PAID = "pagado"
    REJECTED = "rechazado"
    REFUNDED = "reembolsado"


class PaymentProvider(str, enum.Enum):
    WOMPI = "wompi"
    MERCADO_PAGO = "mercado_pago"
    PAYU = "payu"
    STRIPE = "stripe"
    MANUAL = "manual"


class ValidationResult(str, enum.Enum):
    AUTHORIZED = "acceso_autorizado"
    ALREADY_USED = "boleta_ya_utilizada"
    EVENT_DISABLED = "evento_no_habilitado"
    INVALID = "boleta_invalida"
