
from workers import Response, WorkerEntrypoint
from urllib.parse import urlparse
from datetime import datetime, timezone
from html import escape
import base64
import json


def access_login_time(request):
    """Return the login time from the Cloudflare Access JWT (iat claim).

    The signature is not verified here: like the email header, this token
    is trusted because Cloudflare Access sits in front of the Worker.
    Returns None if the token is missing or malformed.
    """
    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if not token:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # restore base64 padding
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return datetime.fromtimestamp(int(claims["iat"]), timezone.utc)
    except (IndexError, KeyError, ValueError, TypeError):
        return None


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)
        path = url.path.rstrip("/") or "/"

        # Serve country flags from the private R2 bucket.
        if path.startswith("/secure/"):
            country = path.removeprefix("/secure/").upper()

            # Accept only two-letter country codes.
            if len(country) != 2 or not country.isalpha():
                return Response("Invalid country code", status=400)

            # Retrieve the corresponding SVG file from R2.
            obj = await self.env.fde_secure_flags.get(
                f"{country}.svg"
            )

            if obj is None:
                return Response("Flag not found", status=404)

            return Response(
                obj.body,
                headers={
                    "Content-Type": "image/svg+xml",
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "private, max-age=300",
                },
            )

        # Only handle the /secure page.
        if path != "/secure":
            return Response("Not found", status=404)

        # Cloudflare Access must protect this route.
        email = request.headers.get(
            "Cf-Access-Authenticated-User-Email"
        )

        # Login time comes from the Access token, not the request time.
        login_time = access_login_time(request)

        if not email or login_time is None:
            return Response(
                "Access identity missing. Check your Cloudflare Access policy.",
                status=401,
            )

        # Get the visitor's country from Cloudflare.
        cf = getattr(request, "cf", None)
        country = getattr(cf, "country", None) if cf else None
        country = country or "XX"

        timestamp = login_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        safe_email = escape(email)
        safe_country = escape(country)

        # Link only real country codes. Cloudflare uses "XX" for unknown
        # and "T1" for Tor, which have no flag in R2.
        if country.isalpha() and len(country) == 2 and country != "XX":
            country_html = f'<a href="/secure/{safe_country}">{safe_country}</a>'
        else:
            country_html = safe_country

        # Build the authenticated user's page.
        page = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Secure identity</title>
</head>
<body>
    <p>{safe_email} authenticated at {timestamp} from {country_html}</p>
</body>
</html>"""

        return Response(
            page,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
