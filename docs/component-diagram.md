# Diagrama de Componentes — TAVA

```mermaid
flowchart TB
    subgraph Cliente["Frontend Angular 19"]
        UI[UI TAVA Theme]
        AuthM[Auth + Interceptor JWT]
        EventsM[Módulo Eventos]
        BuyM[Flujo Compra]
        ValM[Validación QR móvil]
        AdminM[Dashboard Admin]
        LoyaltyM[Coleccionables]
        NotifM[Popups institucionales]
    end

    subgraph API["Backend FastAPI — Hexagonal"]
        REST[Presentation / Routers]
        UC[Application / Use Cases]
        DOM[Domain / Entities + Ports]
        INF[Infrastructure]
    end

    subgraph INF_DETAIL["Infrastructure"]
        PG[(PostgreSQL)]
        JWT_S[JWT + Refresh]
        QR_G[QR + Security Hash]
        MAIL[Email SMTP]
        PAY[Pasarelas Wompi MP PayU Stripe]
        CAP[Captcha]
        FILES[Uploads media]
    end

    UI --> AuthM
    UI --> EventsM
    UI --> BuyM
    UI --> ValM
    UI --> AdminM
    UI --> LoyaltyM
    UI --> NotifM

    AuthM --> REST
    EventsM --> REST
    BuyM --> REST
    ValM --> REST
    AdminM --> REST
    LoyaltyM --> REST

    REST --> UC
    UC --> DOM
    UC --> INF
    INF --> PG
    INF --> JWT_S
    INF --> QR_G
    INF --> MAIL
    INF --> PAY
    INF --> CAP
    INF --> FILES
```

## Capas hexagonales (backend)

| Capa | Responsabilidad |
|------|-----------------|
| `domain` | Entidades, enums, interfaces de repositorio |
| `application` | Casos de uso (auth, validación, fidelización) |
| `infrastructure` | SQLAlchemy, JWT, captcha, email, pagos |
| `presentation` | Routers FastAPI, schemas Pydantic, OpenAPI |
