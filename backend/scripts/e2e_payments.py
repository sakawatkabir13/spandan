"""A hosted-provider fixture installed only by the guarded browser-test server."""

import hashlib
import hmac
import html
import json
import os
import time
from uuid import uuid4

from fastapi import Form
from fastapi.responses import HTMLResponse, RedirectResponse
from httpx import ASGITransport, AsyncClient


def install(app, settings):
    from app.services import billing as payments

    settings.STRIPE_SECRET_KEY = "sk_test_browser_fixture"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_browser_fixture"
    settings.FRONTEND_URL = os.environ.get("E2E_URL", "http://127.0.0.1:5175")
    sessions = {}

    async def provider(method, path, data=None, key=None):
        if path == "checkout/sessions":
            id = "cs_browser_" + uuid4().hex
            sessions[id] = {"id": id, "url": f"http://127.0.0.1:18000/__e2e/checkout/{id}", "status": "open", "payment_status": "unpaid", "livemode": False, "currency": data["line_items[0][price_data][currency]"], "amount_total": int(data["line_items[0][price_data][unit_amount]"]), "metadata": {"payment_id": data["metadata[payment_id]"]}, "payment_intent": "pi_browser_" + id, "success_url": data["success_url"].replace("{CHECKOUT_SESSION_ID}", id), "cancel_url": data["cancel_url"]}
            return sessions[id]
        if path == "refunds":
            return {"id": "re_browser_" + uuid4().hex, "status": "succeeded"}
        id = path.split("/")[2]
        if path.endswith("/expire"):
            sessions[id]["status"] = "expired"
        return sessions[id]

    payments.stripe = provider

    def checkout_html(id, error=""):
        cancel = html.escape(sessions[id]["cancel_url"], quote=True)
        return HTMLResponse(f'''<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hosted checkout fixture</title><body><h1>Secure checkout</h1><p role="alert">{html.escape(error)}</p><form method="post"><label>Card number<input name="card_number" required></label><button>Pay now</button></form><a href="{cancel}">Return without paying</a></body></html>''')

    @app.get("/__e2e/checkout/{id}")
    async def show(id: str):
        return checkout_html(id)

    @app.post("/__e2e/checkout/{id}")
    async def pay(id: str, card_number: str = Form(...)):
        session = sessions[id]
        if card_number.replace(" ", "") != "4242424242424242":
            return checkout_html(id, "Your card was declined. Please use another card.")
        session["status"] = "complete"
        session["payment_status"] = "paid"
        event = {"type": "checkout.session.completed", "livemode": False, "data": {"object": session}}
        raw = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/payments/webhook", content=raw, headers={"stripe-signature": f"t={timestamp},v1={signature}"})
            response.raise_for_status()
        return RedirectResponse(session["success_url"], status_code=303)
