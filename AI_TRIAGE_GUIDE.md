# AI specialty guidance

The implementation is in [backend/app/services/ai.py](backend/app/services/ai.py).

1. The service checks the supplied text against its emergency keyword list. A match bypasses the language model and returns the existing emergency message.
2. With `GROQ_API_KEY` configured, it requests a specialty from the active database specializations using `openai/gpt-oss-120b`. Groq strict structured output must pass the `TriageModelResponse` JSON schema. Unknown specialties, malformed output, network failures, rate limits, and timeouts use the fallback after bounded retries.
3. Without a usable model response, the service returns **General Medicine**, urgency **soon**, and an explicit service-unavailability explanation. The fallback does not infer a specialty from symptoms.

The public symptom-check endpoint works without an account. For signed-in patients, recommendations appear in their history. Emergency results have no appointment-booking action. Other results link to the recommended specialization filter when its ID is available.

## Configuration

Set `GROQ_API_KEY` in the root `.env` used by Docker Compose. `GROQ_MODEL` defaults to `openai/gpt-oss-120b`. Apply changes with:

```bash
docker compose up -d --force-recreate backend
```

For local Python execution, export these variables or put them in `backend/.env`.

## Validation and limitations

Tests cover the emergency branch, guest access, saved patient history, unavailable-service fallback, and malformed model responses. Automated tests use no live API key and do not transmit symptoms to Groq. Live provider behavior needs a configured key and separate validation.

This is a specialty guidance feature, not a diagnostic system. Keyword matching can miss emergencies and can match negated phrases. Valid JSON does not establish clinical accuracy. No clinical validation or safety guarantee is claimed.
