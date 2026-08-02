# Spandan: An AI-Assisted Appointment Booking & Private Chamber Management System

**Spandan** is a complete, production-ready full-stack web application tailored for Bangladesh’s healthcare ecosystem. It streamlines consultation scheduling for private doctor chambers while incorporating safe AI triage (`Groq API` / `Llama`) to recommend appropriate medical specialties based on patient symptoms.

---

## 🌟 Key Features

- **Multi-Role RBAC**: Dedicated portals and permissions for **Patients**, **Doctors**, **Assistants**, and **Administrators**.
- **Verified Doctor Profiles & Multiple Chambers**: Strict administrator verification workflow before doctors appear publicly or open schedules.
- **Unified Online & Offline Queue Engine**: Real-time serial allocation, delay tracking, and dynamic estimated consultation times with zero double-booking (PostgreSQL atomic transactions).
- **AI Symptom Triage**: Rule-based emergency screening and Groq Llama-powered specialty recommendations with strict disclaimers.
- **Dockerized Infrastructure**: Complete container orchestration with PostgreSQL, FastAPI backend, and React TypeScript frontend.

---

## 🏗️ Technology Stack

- **Frontend**: React 18, TypeScript, Vite, TanStack Query, React Hook Form, Zod, Tailwind CSS, Lucide Icons.
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.x (AsyncPG), Pydantic v2, Alembic, Argon2/Bcrypt password hashing, JWT RBAC.
- **Database**: PostgreSQL 16 with strict constraints and row-level concurrency locking (`SELECT FOR UPDATE`).
- **AI Engine**: Groq API (`GROQ_MODEL`) with structured JSON schema enforcement.
- **Testing**: Pytest (Backend integration/unit tests), Vitest & React Testing Library (Frontend).

---

## 🚀 Quick Start & Deployment Guide

### 1. Prerequisites
- Docker & Docker Compose installed (v2.x+)
- Make utility (optional, for convenience commands)

### 2. Environment Setup
Copy the sample environment file:
```bash
cp .env.example .env
```
*(Optional: Add your `GROQ_API_KEY` to `.env` if you want live AI triage. A fallback triage engine operates automatically if the API key is omitted).*

### 3. Launch with Docker Compose
To start the database, backend, and frontend containers:
```bash
make up
# Or directly: docker compose up --build -d
```

During startup, the backend container automatically:
1. Waits for PostgreSQL healthcheck.
2. Runs Alembic database schema migrations (`alembic upgrade head`).
3. Executes the idempotent seed data script (`python -m scripts.seed`).

### 4. Accessing the Applications
- **Frontend Web Portal**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔑 Demo & Seed Credentials

The initial seed script creates the following accounts (all default passwords are `Password123!`):

| Role | Email | Password | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin@spandan.com.bd` | `Password123!` | Active | Full system access & verification review |
| **Doctor (Approved)**| `dr.rahman@spandan.com.bd` | `Password123!` | Approved | Cardiologist & General Medicine (Dhanmondi Chamber) |
| **Doctor (Approved)**| `dr.farhana@spandan.com.bd`| `Password123!` | Approved | Pediatrician (Uttara Chamber) |
| **Doctor (Pending)** | `dr.tariq@spandan.com.bd`  | `Password123!` | Pending | Awaiting verification by Admin |
| **Assistant** | `assistant.karim@spandan.com.bd` | `Password123!` | Active | Assigned to Dr. Rahman |
| **Assistant** | `assistant.nasrin@spandan.com.bd`| `Password123!` | Active | Assigned to Dr. Farhana |
| **Patient** | `patient.jamal@gmail.com`  | `Password123!` | Active | Sample patient with bookings |
| **Patient** | `patient.sadia@gmail.com`  | `Password123!` | Active | Sample patient with AI recommendation logs |

---

## 🛠️ Management & Testing Commands

Using `Makefile` shortcuts:
```bash
make logs       # Follow logs across all containers
make migrate    # Run new Alembic migrations inside container
make seed       # Re-run or reset seed data
make test       # Execute complete Pytest suite for backend
make down       # Stop and remove containers
make clean      # Clean up volumes and build artifacts
```

Or using direct Docker commands:
```bash
docker compose exec backend pytest -v
docker compose exec backend alembic upgrade head
```

---

## ⚠️ Medical & Safety Disclaimers

1. **Not for Medical Diagnosis**: Spandan's AI Specialist Recommendation tool provides **general guidance only** based on user-entered symptoms. It does **never** diagnose illnesses or prescribe medications.
2. **Emergency Guidance**: If you experience life-threatening symptoms (e.g., severe chest pain, difficulty breathing, stroke symptoms), contact local emergency services immediately (`999` in Bangladesh) or visit the nearest hospital emergency department.
