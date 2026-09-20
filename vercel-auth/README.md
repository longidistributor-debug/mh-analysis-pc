# MH Analysis License Backend

Vercel-ready licensing backend for MH Analysis.

## Vercel project

Deploy the dedicated GitHub branch `vercel-license-deploy` as project:

`mh-analysis-license-longidistributor-8873`

That exact project name matches the default backend URL embedded in MH Analysis V80:

`https://mh-analysis-license-longidistributor-8873.vercel.app`

## Manual Vercel environment variable

Only one required secret needs to be added manually in Vercel:

- `MONGODB_URI` — MongoDB Atlas connection string.

Optional:
- `LICENSE_TIMEZONE` — defaults to `Asia/Karachi`.

The JWT signing secret is generated on first database connection and stored server-side in MongoDB `system_config`. It is not compiled into the EXE or committed to GitHub.

The bootstrap admin secret itself is not committed; only its SHA-256 hash is in source. The administrator must keep the original admin secret privately.

## Security model

- No public registration
- No forgot-password/self-reset
- Admin-created users only
- bcrypt password hashing
- Server-authoritative validity dates
- One device maximum
- First successful login binds an Ed25519 device public key
- Windows client keeps the private device key protected by DPAPI
- Refresh requires a signed server challenge
- Remote disable, expiry and device reset invalidate continued access
- Login throttling and security activity logging
- EXE local API operations are license-gated and require periodic online authorization

## Routes

- `/admin`
- `/api/health`
- `/api/auth/login`
- `/api/auth/verify`
- `/api/auth/challenge`
- `/api/auth/refresh`
- `/api/auth/logout`
- `/api/admin/login`
- `/api/admin/users`
- `/api/admin/activity`
