# MH Analysis License Server

Vercel-ready licensing/authentication backend for MH Analysis.

## Required Vercel environment variables

- `MONGODB_URI` — MongoDB Atlas connection string.
- `JWT_SECRET` — strong random secret used to sign short-lived application/admin sessions.
- `ADMIN_SECRET` — strong random administrator login secret.
- `MONGODB_DB` — optional, defaults to `mh_analysis_license`.
- `LICENSE_TIMEZONE` — optional, defaults to `Asia/Karachi`.

Do not commit real secrets to GitHub.

## Admin

Open `/admin`. There is no public registration or user self-service reset. The administrator can create users, set inclusive Valid From / Valid Until dates, renew access, disable/enable users, reset a password, reset the single authorized device, delete users, and review security activity.

The `validUntil` date is inclusive in `LICENSE_TIMEZONE`; access returns `LICENSE_EXPIRED` on the next calendar day with the message `Expired — contact administrator for renewal.`

## Desktop device protocol

1. The desktop app creates an Ed25519 key pair on first use and protects the private key with Windows DPAPI.
2. `POST /api/auth/challenge` with `username` and `device_id`.
3. Sign the returned `challenge` with the device private key.
4. `POST /api/auth/login` with username/password, challenge id, signature, public key, device id, and basic device info.
5. First successful login binds that public key to the account. A different key is rejected with `DEVICE_NOT_AUTHORIZED` even if username/password are correct.
6. Use the returned Bearer token with `POST /api/auth/verify` periodically. Disable, expiry, password reset, or device reset revokes/blocks access server-side.

One account is fixed to one device. There is intentionally no registration, forgot-password, self-renewal, or self-device-reset endpoint.
