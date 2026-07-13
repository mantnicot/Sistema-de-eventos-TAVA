"""Ajustes incrementales de esquema (sin Alembic) para despliegues existentes."""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger("tava.schema")


async def apply_schema_upgrades(conn: AsyncConnection) -> None:
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS theatrical_details JSONB",
        """
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_policy_version VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS marketing_opt_in_at TIMESTAMPTZ",
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS holder_name VARCHAR(200)",
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS site_settings (
            key VARCHAR(80) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS event_staff_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            staff_role VARCHAR(20) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_event_staff_role UNIQUE (user_id, event_id, staff_role)
        )
        """,
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS ticket_code VARCHAR(12)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_ticket_code ON tickets(ticket_code) WHERE ticket_code IS NOT NULL",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(64)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS wompi_transaction_id VARCHAR(128)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS pending_payload JSONB",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_payment_reference ON orders(payment_reference) WHERE payment_reference IS NOT NULL",
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS event_seat_id UUID REFERENCES event_seats(id)",
        "ALTER TABLE event_seats ADD COLUMN IF NOT EXISTS ticket_type_id UUID REFERENCES ticket_types(id) ON DELETE SET NULL",
        """
        CREATE TABLE IF NOT EXISTS event_seats (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            block_id VARCHAR(40) NOT NULL,
            row_label VARCHAR(10) NOT NULL,
            col_label VARCHAR(10) NOT NULL,
            label VARCHAR(120) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'disponible',
            CONSTRAINT uq_event_seat_pos UNIQUE (event_id, block_id, row_label, col_label)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_events_status_date ON events(status, event_date)",
        "CREATE INDEX IF NOT EXISTS ix_ticket_types_event_id ON ticket_types(event_id)",
        "CREATE INDEX IF NOT EXISTS ix_tickets_owner_id ON tickets(owner_id)",
        "CREATE INDEX IF NOT EXISTS ix_tickets_event_used ON tickets(event_id, is_used)",
        "CREATE INDEX IF NOT EXISTS ix_orders_buyer_id ON orders(buyer_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_staff_user_role ON event_staff_assignments(user_id, staff_role)",
    ]
    for sql in statements:
        await conn.execute(text(sql.strip()))
    logger.info("Esquema actualizado (columnas/tablas nuevas)")
