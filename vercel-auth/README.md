# MH Analysis License Backend

Vercel-ready licensing backend for MH Analysis.

## Manual Vercel environment variable

Only one required secret needs to be added manually in Vercel:

- `MONGODB_URI` — MongoDB Atlas connection string.

Optional:
- `LICENSE_TIMEZONE` — defaults to `Asia/Karachi`.

The JWT signing secret is generated on first database connection and stored server-side in MongoDB `system_config`.
The bootstrap admin secret itself is not committed; only its SHA-256 hash is in source. The admin can later rotate it.

## Security model

- No public registration
- No forgot-password/self-reset
- Admin-created users only
- bcrypt password hashing
- Server-authoritative validity dates
- One device maximum
- First successful login binds an Ed25519 device public key
- Windows client keeps the private device key under DPAPI
- Refresh requires a signed server challenge
- Remote disable, expiry and device reset invalidate continued access
- Login throttling and activity logging

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

Deploy this folder as the Vercel project root using project name `mh-analysis-license-longidistributor-8873` so the Windows client default URL matches the deployment.
