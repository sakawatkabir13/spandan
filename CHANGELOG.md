# Changelog

All notable changes to Spandan will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `docs/ARCHITECTURE.md` with Mermaid diagrams for auth flow, queue-engine locking, AI triage pipeline, doctor verification state machine, appointment state machine, data-model ERD, and deployment topology.
- Linked architecture doc from the README architecture section and project tree.

### Planned
- Real-time queue updates via WebSockets / SSE.
- Doctor availability calendar view.
- SMS & email notification providers.
- Mobile-first PWA shell for patients.

## [0.1.0] - 2026-08-15

### Added
- Multi-role RBAC for **Patients**, **Doctors**, **Assistants**, and **Administrators**.
- Doctor verification workflow with admin approval/rejection.
- Multi-chamber support per doctor with independent schedules.
- Unified online & offline queue engine with atomic serial allocation (`SELECT FOR UPDATE`).
- 3-tier AI symptom triage:
  - Tier 1: Local rule-based emergency screening (0 ms).
  - Tier 2: Groq Cloud AI engine (`llama-3.3-70b-versatile`).
  - Tier 3: Local keyword fallback engine.
- JWT authentication with refresh tokens and Argon2/Bcrypt hashing.
- Alembic migrations with idempotent seed data.
- Docker Compose orchestration for PostgreSQL, FastAPI backend, and Vite/React frontend.
- Pytest backend test suite and Vitest frontend tests.

### Security
- Argon2/Bcrypt password hashing.
- Strict CORS allow-list.
- JWT secret configurable via environment.

[Unreleased]: https://github.com/sakawatkabir13/19-spandan/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sakawatkabir13/19-spandan/releases/tag/v0.1.0
