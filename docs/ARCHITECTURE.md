<div align="center">

# 🏛️ Spandan — System Architecture

### Internal design notes for engineers, contributors, and reviewers.

[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](../backend)
[![Frontend](https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=flat-square&logo=react&logoColor=white)](../frontend)
[![Database](https://img.shields.io/badge/DB-PostgreSQL%2016-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![AI](https://img.shields.io/badge/AI-Groq%20Llama%203.3-FF6B35?style=flat-square)](https://groq.com)
[![Migrations](https://img.shields.io/badge/Migrations-Alembic-2C2C2C?style=flat-square)](#data-model)

</div>

---

## 📑 Table of Contents

1. [System Overview](#-system-overview)
2. [Layered Architecture](#-layered-architecture)
3. [Component Diagram](#-component-diagram)
4. [Request Lifecycle](#-request-lifecycle)
5. [Auth & RBAC Flow](#-auth--rbac-flow)
6. [Queue Engine (No-Double-Booking)](#-queue-engine-no-double-booking)
7. [AI Symptom Triage (3-Tier)](#-ai-symptom-triage-3-tier)
8. [Doctor Verification Lifecycle](#-doctor-verification-lifecycle)
9. [Appointment Booking State Machine](#-appointment-booking-state-machine)
10. [Data Model (ERD)](#-data-model-erd)
11. [Deployment Topology](#-deployment-topology)
12. [Security Boundaries](#-security-boundaries)
13. [Observability Hooks](#-observability-hooks)
14. [Glossary](#-glossary)

---

## 🏛️ System Overview

Spandan is a **single-tenant, role-aware healthcare operations platform** that connects four distinct user personas (Patients, Doctors, Assistants, Administrators) through a single FastAPI REST backend, a React 18 SPA, and a PostgreSQL 16 datastore.

The system has three primary responsibilities that drive its architecture:

| Responsibility                  | Architectural Mechanism                                        |
| ------------------------------- | -------------------------------------------------------------- |
| **Safe concurrency** for booking | PostgreSQL row-level locking (`SELECT FOR UPDATE`) + serial uniqueness per schedule |
| **Safety-first AI suggestions**  | 3-tier triage pipeline (local rule → Groq LLM → local fallback) |
| **Trust through verification**   | Explicit state machine `PENDING → APPROVED / REJECTED / SUSPENDED` on every doctor profile |

Everything else — role-based dashboards, multi-chamber scheduling, JWT auth, assistant delegation — exists to make those three guarantees usable from a browser.

---

## 🧱 Layered Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                          Browser (React 18)                         │
│  TanStack Query (cache + retry) · React Hook Form · Zod (client)   │
└────────────────────────────┬───────────────────────────────────────┘
                             │  HTTPS · Bearer JWT · JSON over REST
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│                    FastAPI 0.110 (Async, Python 3.11)               │
│  ┌──────────────┐  ┌───────────────  ┌────────────────────────┐   │
│  │  API Routes  │  │ Dependencies │  │  Pydantic v2 Schemas   │   │
│  │ /auth/...    │  │ (auth, RBAC) │  │  (request/response)    │   │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘   │
│         └─────────────────┼────────────────────────────────────────────┘ │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Service Layer (business rules)              │  │
│  │   auth · doctor · chamber · schedule · appointment · ai      │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
│                             ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Repository Layer (data access)                  │  │
│  │   Async SQLAlchemy 2 · asyncpg · selectinload · row locks    │  │
│  └──────────────────────────┬───────────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────────┘
                              ▼
                ┌─────────────────────────────┐
                │   PostgreSQL 16             │
                │   row-level locking         │
                │   Alembic migrations        │
                └─────────────────────────────┘
```

**Rule of thumb for contributors:** routes are thin, services own business rules, repositories own SQL. Schemas are the *only* place types are declared.

---

## 🧩 Component Diagram

```mermaid
graph LR
  subgraph Client
    SPA["React 18 SPA<br/>(Vite + TS + Tailwind)"]
  end

  subgraph Backend["FastAPI Backend"]
    Auth["Auth Routes<br/>/api/v1/auth"]
    Doctors["Doctor Routes<br/>/api/v1/doctors"]
    Chambers["Chamber Routes<br/>/api/v1/chambers"]
    Schedules["Schedule Routes<br/>/api/v1/schedules"]
    Appointments["Appointment Routes<br/>/api/v1/appointments"]
    AI["AI Triage Routes<br/>/api/v1/ai"]

    AuthSvc["AuthService"]
    DoctorSvc["DoctorService"]
    ScheduleSvc["ScheduleService"]
    ApptSvc["AppointmentService"]
    TriageSvc["SymptomTriageService"]
  end

  subgraph External
    Groq["Groq LLM API<br/>llama-3.3-70b-versatile"]
  end

  DB[("PostgreSQL 16")]

  SPA -->|JWT| Auth
  SPA --> Doctors
  SPA --> Chambers
  SPA --> Schedules
  SPA --> Appointments
  SPA --> AI

  Auth --> AuthSvc
  Doctors --> DoctorSvc
  Chambers --> DoctorSvc
  Schedules --> ScheduleSvc
  Appointments --> ApptSvc
  AI --> TriageSvc

  AuthSvc --> DB
  DoctorSvc --> DB
  ScheduleSvc --> DB
  ApptSvc --> DB
  TriageSvc --> DB
  TriageSvc -.HTTPS.-> Groq
```

---

## 🔁 Request Lifecycle

Every authenticated request follows the same path:

```mermaid
sequenceDiagram
  autonumber
  participant U as User (Browser)
  participant R as React + TanStack Query
  participant F as FastAPI Route
  participant D as Dependency (get_current_user)
  participant S as Service Layer
  participant Repo as Repository
  participant DB as PostgreSQL

  U->>R: Click "Book appointment"
  R->>F: POST /api/v1/appointments (Authorization: Bearer …)
  F->>D: Resolve Bearer token
  D->>D: Decode JWT, load user + role
  D-->>F: current_user: User
  F->>F: Pydantic validates request body
  F->>S: appointment_service.book_appointment(db, user, payload)
  S->>Repo: schedule_repo.get_by_id_with_queue()
  Repo->>DB: SELECT … FOR UPDATE
  DB-->>Repo: schedule row (locked)
  Repo-->>S: schedule
  S->>Repo: appointment_repo.check_patient_already_booked()
  S->>Repo: appointment_repo.get_max_serial()
  Repo-->>S: max_serial
  S->>DB: INSERT INTO appointments
  S-->>F: Appointment ORM (refreshed)
  F-->>R: 201 Created + JSON
  R->>R: Invalidate queries, show toast
  R-->>U: Updated UI
```

Key invariants:

1. The DB session is request-scoped (`get_db()` dependency).
2. The `Schedule` row is locked **before** any serial allocation, so two concurrent bookings can never receive the same serial number.
3. Errors raise `SpandanException` → mapped to a structured JSON error by FastAPI's exception handler.

---

## 🔐 Auth & RBAC Flow

Spandan uses **dual-token JWT** (access + refresh) with Argon2/Bcrypt password hashing.

```mermaid
sequenceDiagram
  autonumber
  participant U as Patient
  participant FE as React
  participant API as /auth/login
  participant DB as PostgreSQL
  participant Protected as Protected Route

  U->>FE: Submit email + password
  FE->>API: POST /api/v1/auth/login
  API->>DB: SELECT user WHERE email = ?
  DB-->>API: user (with password_hash)
  API->>API: verify_password(plain, hash)
  alt Invalid credentials
    API-->>FE: 401 Unauthorized
  else Valid
    API->>API: create_access_token (15 min)
    API->>API: create_refresh_token (7 days)
    API-->>FE: { access_token, refresh_token, user, role }
    FE->>FE: Store tokens (memory + refresh cookie)
    FE->>Protected: GET /api/v1/appointments/mine
    Protected->>Protected: get_current_user (decode access JWT)
    alt Token expired
      Protected-->>FE: 401 → refresh flow
      FE->>API: POST /auth/refresh { refresh_token }
      API->>API: decode refresh, type == "refresh"
      API-->>FE: new access + refresh tokens
      FE->>Protected: retry original request
    else Valid
      Protected->>DB: filter by current_user.id
      DB-->>Protected: scoped rows
      Protected-->>FE: 200 OK
    end
  end
```

**Roles** (enum `UserRole`):

| Role            | Can read                       | Can write                                  |
| --------------- | ------------------------------ | ------------------------------------------ |
| `PATIENT`       | own appointments, public doctors | own appointments (cancel only)             |
| `DOCTOR`        | own schedule + appointments    | own profile, schedule, appointment status  |
| `ASSISTANT`     | assigned doctor's schedule     | walk-in bookings + status for that doctor   |
| `ADMINISTRATOR` | everything                     | doctor verification, all entities          |

Permission checks live in **services**, not routes, so a single business rule cannot be bypassed by a new endpoint.

---

## 🚦 Queue Engine (No-Double-Booking)

The queue engine guarantees two invariants that together eliminate the class of "double-booked serial" bugs:

1. **At most one active appointment per `(schedule_id, patient_id)`** — enforced in `AppointmentService.book_appointment()` via `check_patient_already_booked()`.
2. **Strictly monotonic serial numbers per `schedule_id`** — enforced inside a row-locked transaction on `Schedule`.

```mermaid
sequenceDiagram
  autonumber
  participant P as Patient A
  participant W as Walk-in Assistant B
  participant API as AppointmentService
  participant DB as PostgreSQL

  par Concurrent booking attempt
    P->>API: book_appointment(schedule_id, patient_A)
    API->>DB: BEGIN
    API->>DB: SELECT * FROM schedules WHERE id = ? FOR UPDATE
    DB-->>API: schedule row (X-lock held)
  and
    W->>API: book_appointment(schedule_id, patient_B)
    API->>DB: BEGIN
    API->>DB: SELECT * FROM schedules WHERE id = ? FOR UPDATE
    Note over DB: BLOCKS — waiting for A's lock
  end

  API->>API: already_booked? count_active? max_serial?
  API->>DB: INSERT INTO appointments (serial = max_serial + 1)
  API->>DB: COMMIT (releases X-lock)
  DB-->>W: schedule row (X-lock acquired)
  API->>API: already_booked? count_active? max_serial?
  API->>DB: INSERT INTO appointments (serial = previous_max + 1)
  API->>DB: COMMIT
  DB-->>P: 201 Created (serial N)
  DB-->>W: 201 Created (serial N+1)
```

**Serial tracking** (`GET /api/v1/appointments/serial-tracking/{schedule_id}`):

```mermaid
flowchart LR
  A["Schedule row<br/>(max_patients, avg_consultation_minutes)"]
  Q["QueueState row<br/>(current_serial, delay_minutes, status_message)"]
  Apps["Appointments<br/>ordered by serial_number"]
  Out["SerialTrackingResponse<br/>your_serial · people_ahead<br/>est_waiting_mins · est_consult_time"]

  A --> Q
  Q --> Out
  Apps --> Out
```

When a doctor flips status to `IN_CONSULTATION`, `QueueState.current_serial` is auto-synced to that appointment's serial, and `status_message` updates accordingly.

---

## 🤖 AI Symptom Triage (3-Tier)

Safety is the design constraint: **never delay a critical case with a cloud round-trip**, and **never return a hard error** if the LLM is unavailable.

```mermaid
flowchart TD
  Start([Patient submits symptoms]) --> T1{"Tier 1<br/>Local emergency<br/>keyword scan<br/>0 ms"}
  T1 -- "Match:<br/>chest pain, stroke,<br/>unconscious, seizure…" --> Emergency[/"EMERGENCY<br/>Call 999 / nearest ER<br/>Bypass all LLM"/]
  T1 -- "No match" --> T2{"Tier 2<br/>Groq LLM<br/>(llama-3.3-70b-versatile)"}
  T2 -- "GROQ_API_KEY missing" --> T3
  T2 -- "Network / 5xx / timeout" --> T3
  T2 -- "200 OK + JSON" --> Persist["Persist SpecialistRecommendation<br/>recommended_specialization_id<br/>urgency_level · reasoning_summary"]
  T3["Tier 3<br/>Local keyword fallback matrix"] --> Persist
  Emergency --> Persist2["Persist SpecialistRecommendation<br/>urgency_level = EMERGENCY"]
  Persist --> Done([Response])
  Persist2 --> Done
```

**Tier 1 keyword list** (15 terms — see [`backend/app/services/ai.py`](../backend/app/services/ai.py) `EMERGENCY_KEYWORDS`):

```
chest pain · severe breathing difficulty · shortness of breath severe
stroke · slurred speech · sudden weakness · unconscious · fainting
severe bleeding · heart attack · coughing blood · blue lips · seizure
unresponsive · anaphylaxis
```

**Tier 2 prompt contract** (strict JSON, no markdown):

```json
{
  "recommended_specialization_name": "Cardiology",
  "alternative_specialization_name": "General Medicine",
  "urgency_level": "soon",
  "reasoning_summary": "…",
  "safety_message": "…"
}
```

The LLM is given the **live list of active `Specialization` rows** from the DB, so its recommendation always matches a bookable specialty in the system.

**Tier 3 fallback** routes by organ-system keyword counts (`heart`/`palpitation` → Cardiology, `bone`/`joint` → Orthopedics, etc.) and defaults to **General Medicine** when nothing dominates.

---

## ✅ Doctor Verification Lifecycle

Doctors are not publicly visible until an admin approves them. This is enforced both in data (state column) and in queries (`search_doctors(... status=APPROVED ...)`).

```mermaid
stateDiagram-v2
  [*] --> PENDING: Doctor registers<br/>(POST /auth/register/doctor)
  PENDING --> APPROVED: Admin: PATCH /doctors/{id}/verify<br/>status=APPROVED
  PENDING --> REJECTED: Admin: PATCH /doctors/{id}/verify<br/>status=REJECTED + notes
  PENDING --> SUSPENDED: Admin: PATCH /doctors/{id}/verify<br/>status=SUSPENDED
  APPROVED --> SUSPENDED: Admin can suspend
  SUSPENDED --> APPROVED: Admin can re-approve
  REJECTED --> PENDING: Doctor updates profile<br/>and requests re-review

  APPROVED --> [*]
  REJECTED --> [*]
```

Each transition writes `verified_by` (admin user id), `verified_at`, and optional `verification_notes` for an audit trail.

---

## 📅 Appointment Booking State Machine

```mermaid
stateDiagram-v2
  [*] --> BOOKED: Patient or assistant books
  BOOKED --> IN_CONSULTATION: Doctor starts consultation
  BOOKED --> CANCELLED: Patient / assistant / admin cancels
  IN_CONSULTATION --> COMPLETED: Doctor completes consultation
  IN_CONSULTATION --> CANCELLED: Admin force-cancels
  COMPLETED --> [*]
  CANCELLED --> [*]
```

Side effects:

- `BOOKED` increments `Schedule.active_count`; if the schedule hits `maximum_patients`, status becomes `FULL`.
- `CANCELLED` releases the serial back into the pool; if the schedule was `FULL`, status reverts to `OPEN` (unless past end time).
- `IN_CONSULTATION` syncs `QueueState.current_serial` and writes `actual_consultation_started_at`.
- `COMPLETED` writes `actual_consultation_completed_at`.

---

## 🗄️ Data Model (ERD)

```mermaid
erDiagram
  USERS ||--o| PATIENT_PROFILES : has
  USERS ||--o| DOCTOR_PROFILES : has
  USERS ||--o{ ASSISTANT_ASSIGNMENTS : "is assigned"

  DOCTOR_PROFILES ||--o{ DOCTOR_SPECIALIZATIONS : has
  SPECIALIZATIONS ||--o{ DOCTOR_SPECIALIZATIONS : "tagged on"

  DOCTOR_PROFILES ||--o{ QUALIFICATIONS : has
  DOCTOR_PROFILES ||--o{ CHAMBERS : owns
  DOCTOR_PROFILES ||--o{ SCHEDULES : "publishes"
  CHAMBERS ||--o{ SCHEDULES : "hosts"

  SCHEDULES ||--|| QUEUE_STATES : has
  SCHEDULES ||--o{ APPOINTMENTS : "queues"
  DOCTOR_PROFILES ||--o{ APPOINTMENTS : "sees"
  CHAMBERS ||--o{ APPOINTMENTS : "at"
  PATIENT_PROFILES ||--o{ APPOINTMENTS : "books"
  USERS ||--o{ APPOINTMENTS : "booked_by"

  PATIENT_PROFILES ||--o{ SPECIALIST_RECOMMENDATIONS : "receives"

  USERS {
    uuid id PK
    string email UK
    string phone_number UK
    string password_hash
    enum role "PATIENT | DOCTOR | ASSISTANT | ADMINISTRATOR"
    bool is_active
    timestamp last_login_at
  }

  DOCTOR_PROFILES {
    uuid id PK
    uuid user_id FK
    string medical_registration_number
    enum verification_status "PENDING | APPROVED | REJECTED | SUSPENDED"
    uuid verified_by FK
    timestamp verified_at
    text verification_notes
  }

  SCHEDULES {
    uuid id PK
    uuid doctor_id FK
    uuid chamber_id FK
    date schedule_date
    time start_time
    time end_time
    int average_consultation_minutes
    int maximum_patients
    enum status "OPEN | FULL | CLOSED | CANCELLED"
  }

  QUEUE_STATES {
    uuid id PK
    uuid schedule_id FK
    int current_serial
    int delay_minutes
    string status_message
  }

  APPOINTMENTS {
    uuid id PK
    uuid patient_id FK
    uuid doctor_id FK
    uuid chamber_id FK
    uuid schedule_id FK
    int serial_number
    enum booking_source "ONLINE | WALK_IN | PHONE"
    enum appointment_status "BOOKED | IN_CONSULTATION | COMPLETED | CANCELLED"
    timestamp estimated_consultation_at
    uuid booked_by_user_id FK
    text cancellation_reason
  }

  SPECIALIST_RECOMMENDATIONS {
    uuid id PK
    uuid patient_id FK
    text symptoms_text
    string recommended_specialization_name
    uuid recommended_specialization_id FK
    enum urgency_level "ROUTINE | SOON | URGENT | EMERGENCY"
    text reasoning_summary
    text safety_message
    string model_identifier
  }
```

All schema changes are managed by **Alembic** — see [`backend/alembic/`](../backend/alembic) and [`backend/alembic.ini`](../backend/alembic.ini).

---

## 🐳 Deployment Topology

```mermaid
graph TB
  subgraph Host["Linux host / VM"]
    direction TB
    FE["frontend :80<br/>(nginx serving Vite dist)"]
    BE["backend :8000<br/>(uvicorn FastAPI workers)"]
    DB[("db :5432<br/>postgres:16-alpine")]
    Vol[("volume:<br/>postgres-data")]
  end

  Internet((Internet)) --> FE
  FE -->|"/api/* proxied"| BE
  BE -->|"asyncpg"| DB
  DB --- Vol

  BE -.HTTPS.-> Groq[("Groq API<br/>api.groq.com")]
```

- **Frontend** is a static `vite build` bundle served by `nginx`; API calls are reverse-proxied to the backend container.
- **Backend** runs under `uvicorn` (1 worker in dev, configurable `WORKERS` env in prod). Long-running AI calls use `httpx.AsyncClient(timeout=10.0)`.
- **Database** lives in a named volume; Alembic migrations run on container start (`alembic upgrade head`) before the API accepts traffic.

For local development, the same topology is defined in [`docker-compose.yml`](../docker-compose.yml) with hot-reload mounts for both backend and frontend.

---

## 🛡️ Security Boundaries

| Boundary            | Mechanism                                                                 |
| ------------------- | ------------------------------------------------------------------------- |
| Password storage    | Argon2 (preferred) or Bcrypt — never plaintext                            |
| API authentication  | JWT access (short-lived) + JWT refresh (long-lived), HS256/RS256          |
| CORS                | Whitelist via `CORS_ORIGINS` env (no wildcard in prod)                    |
| SQL injection       | SQLAlchemy 2 parameterized queries — no string interpolation in repos      |
| RBAC                | Enforced in service layer, not routes — cannot be bypassed by a new route |
| Doctor trust        | Public listings filter to `verification_status = APPROVED` only           |
| File uploads        | `MAX_UPLOAD_SIZE_MB` + server-side MIME validation (planned hardening)    |
| Secrets             | `.env` is git-ignored; example lives in `.env.example`                    |

See [`SECURITY.md`](../SECURITY.md) for the coordinated vulnerability disclosure policy.

---

## 📈 Observability Hooks

| Concern        | Today                              | Recommended next step                         |
| -------------- | ---------------------------------- | --------------------------------------------- |
| Logs           | stdlib `logging` → stdout          | Ship to Loki / Cloud Logging                  |
| Errors         | `SpandanException` → JSON envelope | Sentry SDK integration                        |
| Metrics        | None yet                           | `prometheus-fastapi-instrumentator`           |
| Audit          | `AuditLog` model exists            | Middleware that writes on every write-route   |
| Tracing        | None yet                           | OpenTelemetry → Tempo / Jaeger               |

The `AuditLog` table is in place — see [`backend/app/models/audit.py`](../backend/app/models/audit.py) — and is ready to back a middleware that records actor, action, target, and diff.

---

## 📚 Glossary

| Term                  | Meaning                                                                  |
| --------------------- | ------------------------------------------------------------------------ |
| **Schedule**          | A doctor's planned session on a specific date/time at a specific chamber |
| **Serial**            | Monotonically increasing position within a schedule                      |
| **Queue State**       | Real-time metadata about a running schedule (current serial, delay)      |
| **Specialization**    | A medical specialty (Cardiology, Neurology, …) registered in the DB     |
| **Verification**      | Admin-controlled state machine on doctor profiles                        |
| **Triage**            | 3-tier pipeline that recommends a specialization from symptom text       |
| **Booking Source**    | `ONLINE` (patient self-service) · `WALK_IN` · `PHONE`                    |

---

<div align="center">

Made with ❤️ for safer healthcare in Bangladesh.

[⬆ Back to top](#-system-overview)

</div>
