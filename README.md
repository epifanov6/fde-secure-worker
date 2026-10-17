# fde-secure-worker

A Python Cloudflare Worker for the Cloudflare FDE home assignment. It serves
identity information for users authenticated by Cloudflare Access, and country
flags from a private R2 bucket.

## Endpoints

| Path | Response | Content type |
|---|---|---|
| `/secure` | `<EMAIL> authenticated at <TIMESTAMP> from <COUNTRY>`, where `<COUNTRY>` links to `/secure/<COUNTRY>` | `text/html; charset=utf-8` |
| `/secure/<COUNTRY>` | Flag SVG for the ISO 3166-1 alpha-2 code, read from R2 | `image/svg+xml` |

## How it works

1. `tunnel.fde-stack.online` is proxied by Cloudflare. A Cloudflare Access
   application protects the hostname, so unauthenticated users are redirected
   to the login page before the request reaches the Worker.
2. Worker routes `tunnel.fde-stack.online/secure` and `/secure/*` send these
   paths to the Worker. All other paths go through the Cloudflare Tunnel to
   the origin.
3. `/secure` builds the page from:
   - `EMAIL`: the `Cf-Access-Authenticated-User-Email` header set by Access.
   - `TIMESTAMP`: the login time, taken from the `iat` claim of the
     `Cf-Access-Jwt-Assertion` token set by Access (UTC).
   - `COUNTRY`: `request.cf.country`, set by Cloudflare from the client IP.
     Unknown (`XX`) and Tor (`T1`) are shown as plain text with no link,
     because they have no flag.
4. `/secure/<COUNTRY>` validates the two-letter code and reads
   `<COUNTRY>.svg` from the `fde-secure-flags` R2 bucket through the Worker
   binding.

## Design decisions

- **Timestamp = login time.** "Authenticated at" is read as the moment the
  user logged in to Access (JWT `iat`), not the time of the current request.
- **Identity comes from Access.** The Worker trusts the headers that Access
  adds, because Access runs in front of the Worker on every routed path. If
  either header is missing, the Worker returns 401.
- **Private bucket.** The R2 bucket has no public r2.dev URL and no custom
  domain. The flags are reachable only through the Worker, so they are also
  behind Access.

## Setup

Prerequisites: Node.js, [uv](https://docs.astral.sh/uv/), a Cloudflare zone,
a Cloudflare Tunnel on the `tunnel.` hostname, and an Access application
covering `tunnel.<domain>/secure`.

```sh
npm install
uv sync

# Create the private bucket and upload flags (uppercase ISO codes)
npx wrangler r2 bucket create fde-secure-flags
npx wrangler r2 object put fde-secure-flags/US.svg --file=US.svg \
  --content-type=image/svg+xml --remote

# Deploy
npm run deploy
```

To use your own domain, change `routes` in `wrangler.jsonc`.

## Testing

Open `https://tunnel.fde-stack.online/secure`, log in through Access, and
click the country link. Without Access (for example `npm run dev` locally),
the Worker returns 401 because the Access headers are missing.
