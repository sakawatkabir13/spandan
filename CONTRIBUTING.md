# Contributing to Spandan

First off, thanks for taking the time to contribute! 🎉
Spandan is an open-source project and every contribution — bug reports, feature requests, documentation, or code — helps.

## 📋 Code of Conduct

This project follows the [Contributor Covenant v2.1](./CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

## 🐛 Reporting Bugs

Before opening an issue, please:

1. Search [existing issues](../../issues) to avoid duplicates.
2. Use the **Bug Report** issue template.
3. Include reproduction steps, expected vs. actual behavior, and environment details (OS, Docker version, Node version, Python version).

## 💡 Suggesting Features

Use the **Feature Request** template and explain:

- The problem you are trying to solve.
- The proposed solution.
- Any alternatives you have considered.

## 🛠️ Local Development Setup

### Prerequisites
- Docker & Docker Compose v2.x+
- Node.js 20+ (for frontend-only work)
- Python 3.11+ (for backend-only work)
- Make (optional, for convenience targets)

### Fork & Clone
```bash
git clone https://github.com/<your-username>/19-spandan.git
cd 19-spandan
cp .env.example .env
```

### Boot the stack
```bash
make up
```

### Run tests
```bash
make test                  # backend
cd frontend && npm test    # frontend
```

## 🧹 Coding Standards

### Backend
- Python 3.11+, follow PEP 8 with a 100-char line limit (enforced by `ruff`).
- Type hints are required for new functions.
- Format with `ruff format` and lint with `ruff check`.
- Write Pytest tests for new features and bug fixes.

### Frontend
- TypeScript strict mode is enabled — keep types clean.
- Use React Hook Form + Zod for forms.
- Use TanStack Query for server state.
- Run `npm run lint` before submitting a PR.

## 🌿 Branch & Commit Conventions

- Branch names: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`, `docs/<short-name>`.
- Commit messages: [Conventional Commits](https://www.conventionalcommits.org/) is encouraged.
  - `feat: add prescription upload endpoint`
  - `fix: prevent double booking on serial collision`
  - `docs: improve onboarding in README`

## 🔁 Pull Request Process

1. Create a feature branch from `main`.
2. Make focused changes with accompanying tests.
3. Ensure `make test` and `npm run lint` pass.
4. Update `README.md` and `CHANGELOG.md` if behavior or configuration changes.
5. Open a PR using the provided template and link the relevant issue.
6. Wait for review — at least one approval is required before merging.

## 📫 Questions?

Open a discussion in the **Q&A** category or reach out via the maintainer email listed in [`SECURITY.md`](./SECURITY.md).

Thank you for making Spandan better! 💚
