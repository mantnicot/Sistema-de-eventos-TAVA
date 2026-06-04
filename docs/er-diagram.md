# Diagrama Entidad-Relación — TAVA

```mermaid
erDiagram
    USERS ||--o{ ORDERS : compra
    USERS ||--o{ TICKETS : posee
    USERS ||--o{ FAVORITES : marca
    USERS ||--o{ COLLECTIBLES : colecciona
    USERS ||--o{ REVIEWS : califica
    USERS ||--o{ CHECK_INS : valida
    USERS ||--o{ REFRESH_TOKENS : tiene

    EVENTS ||--o{ EVENT_MEDIA : contiene
    EVENTS ||--o{ TICKET_TYPES : ofrece
    EVENTS ||--o{ PROMOTIONS : promociona
    EVENTS ||--o{ TICKETS : emite
    EVENTS }o--|| VENUES : usa
    USERS ||--o{ EVENTS : organiza

    VENUES ||--o{ SECTORS : divide
    SECTORS ||--o{ SEATS : contiene
    SEATS }o--o| TICKETS : asigna

    TICKET_TYPES ||--o{ TICKETS : genera
    ORDERS ||--o{ TICKETS : incluye

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        enum role
        boolean is_active
    }

    EVENTS {
        uuid id PK
        string name
        date event_date
        time event_time
        enum status
        int capacity
        uuid organizer_id FK
        uuid venue_id FK
    }

    TICKETS {
        uuid id PK
        string qr_token UK
        string security_hash
        boolean is_used
        uuid order_id FK
        uuid owner_id FK
        uuid event_id FK
        uuid seat_id FK
    }

    VENUES {
        uuid id PK
        string name
        enum venue_type
        int capacity
    }

    SECTORS {
        uuid id PK
        string name
        uuid venue_id FK
    }

    SEATS {
        uuid id PK
        string row_label
        string col_label
        enum status
        uuid sector_id FK
    }

    COLLECTIBLES {
        uuid id PK
        uuid user_id FK
        uuid event_id FK
        string lamina_url
    }

    LOYALTY_REWARDS {
        uuid id PK
        uuid user_id FK
        int events_required
        boolean redeemed
    }
```

## Estados clave

| Entidad | Estados |
|---------|---------|
| Evento | borrador, programado, publicado, agotado, en_curso, finalizado, cancelado |
| Silla | disponible, reservada, vendida, bloqueada |
| Pago | pendiente, pagado, rechazado, reembolsado |
