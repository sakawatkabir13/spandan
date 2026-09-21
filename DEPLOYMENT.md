# Production deployment

Spandan includes a production Compose stack with PostgreSQL on a private network, a non-root FastAPI image, a static Nginx frontend, health checks, request limits, security headers, and no demo data or public backend/database ports.

## Prepare secrets and DNS

Copy the production template and replace every placeholder:

```bash
cp .env.production.example .env.production
```

Generate the JWT secret with `openssl rand -hex 32`. Generate an independent database password and URL-encode it when placing it in `DATABASE_URL`. Store `.env.production` in the cloud secret manager or on the host with restrictive permissions; never commit it. Point the public hostname at the server or load balancer.

The legal pages contain baseline product disclosures. Before accepting real users, replace the operator placeholder language with the deploying organization’s legal name, contact channel, retention schedule, cancellation/refund terms, and governing law. Arrange the privacy and clinical review required for the deployment jurisdiction.

## Deploy

Terminate TLS at a cloud load balancer, ingress controller, or reverse proxy and forward traffic to the frontend container’s port. The production Nginx container proxies API, health, and upload requests to the private backend.

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl --fail https://spandan.example.com/health/ready
```

The backend runs Alembic migrations before starting. Use one backend replica with `RUN_MIGRATIONS=true`; set it to `false` on additional replicas and run `alembic upgrade head` as a release job. Uploads currently use a Docker volume, so multi-host deployments need shared object storage before scaling backend instances across hosts.

Create the first administrator once after the initial deployment. The command prompts for the password without echoing it:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec backend \
  python -m scripts.create_admin \
  --email admin@example.com \
  --phone +8801712345678 \
  --name "System Administrator"
```

The command refuses duplicate email addresses and phone numbers. Use at least 12 characters for the administrator password and store it in a password manager.

## Operations

- Back up PostgreSQL daily, encrypt backups, keep at least one off-site copy, and test restoration regularly.
- Monitor `/health/live` for process health and `/health/ready` for database readiness. Alert on repeated HTTP 5xx, database saturation, Groq fallback rates, and disk usage.
- Forward container logs to the cloud logging service. Each API response includes `X-Request-ID` for correlation.
- Keep the database and backend private. Expose only the TLS endpoint. Restrict host firewall and security-group rules accordingly.
- Run `docker compose pull`, rebuild the images, run migrations, and verify the health endpoint for each release. Keep the previous image tag available for rollback.
- Rotate JWT, database, and Groq secrets through the cloud secret manager. Rotating the JWT secret signs all users out.

The AI feature sends user-entered symptom text to Groq. Obtain the required user notice or consent, define retention with the provider, and avoid logging request bodies. Emergency keyword checks remain local and bypass the model.
