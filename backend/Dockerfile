FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS development
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
RUN pip install --no-cache-dir --no-deps -e .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
COPY requirements-prod.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-prod.lock
COPY . .
RUN pip install --no-cache-dir --no-deps --no-build-isolation . \
    && addgroup --system --gid 10001 spandan \
    && adduser --system --uid 10001 --ingroup spandan --home /app spandan \
    && mkdir -p /app/uploads \
    && chown -R spandan:spandan /app \
    && chmod +x /app/docker-entrypoint.sh
USER spandan
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
