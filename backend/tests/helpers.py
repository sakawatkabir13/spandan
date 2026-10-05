import re


async def verified_post(client, url, **kwargs):
    """Exercise the real registration-code API before existing account workflows."""
    payload = dict(kwargs["json"])
    result = await client.post("/api/v1/auth/registration-code", json={"email": payload["email"]})
    if result.status_code == 200:
        payload["email_otp"] = re.search(r"code is ([0-9]{6})", client.mailbox[-1][2])[1]
    elif result.status_code == 429:
        message = next(
            body
            for recipient, _, body in reversed(client.mailbox)
            if recipient == payload["email"].lower()
        )
        payload["email_otp"] = re.search(r"code is ([0-9]{6})", message)[1]
    else:
        payload["email_otp"] = "000000"
    return await client.post(url, **{**kwargs, "json": payload})
