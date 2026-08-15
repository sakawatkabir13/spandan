# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | ✅ Active          |
| < 0.1.0 | ❌ End of life     |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, email **[security@spandan.com.bd](mailto:security@spandan.com.bd)** (or, if unavailable, the maintainer contact listed on the GitHub profile) with:

1. A clear description of the vulnerability and its impact.
2. Steps to reproduce or a proof-of-concept.
3. Affected component(s) and version.
4. Any suggested remediation, if known.

You should expect an initial acknowledgment within **72 hours** and a status update within **7 business days**.

## Disclosure Policy

- We follow **coordinated disclosure**.
- Please allow us a reasonable time to patch the issue before any public disclosure.
- We will credit reporters (with their consent) in the release notes.

## Security Best Practices for Self-Hosters

- **Generate a strong `JWT_SECRET_KEY`** (e.g., `openssl rand -hex 32`) before deploying.
- Place the backend behind HTTPS / a reverse proxy (Caddy, Nginx, Traefik).
- Restrict the database port (5432) from public exposure.
- Keep `GROQ_API_KEY` and other secrets out of version control — use `.env` or a secret manager.
- Run `docker compose pull` regularly to pick up upstream security patches.

Thank you for helping keep Spandan and its users safe.
