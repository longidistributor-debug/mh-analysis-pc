# MH Analysis License Backend

Vercel-ready licensing backend for MH Analysis.

Deploy the dedicated GitHub branch `vercel-license-deploy` as Vercel project `mh-analysis-license-longidistributor-8873`. That exact name matches the backend URL embedded in MH Analysis V80.

Only one required Vercel environment variable remains manual: `MONGODB_URI`. Optional `LICENSE_TIMEZONE` defaults to `Asia/Karachi`.

The JWT signing secret is generated on first database connection and persisted server-side in MongoDB `system_config`; it is never compiled into the EXE. The bootstrap admin secret itself is not committed; only its SHA-256 hash is stored in source.

Security: admin-created users only, no public registration or self-reset, bcrypt passwords, server-authoritative valid-from/valid-until dates, one-device maximum, Ed25519 device identity with Windows DPAPI-protected private key, challenge-signed refresh, remote disable/renew/device reset, login throttling, activity logging, and periodic online authorization.

Admin panel: `/admin`. Health: `/api/health`.
