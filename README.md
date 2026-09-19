# MH Analysis V79.6 — FINAL CURRENT

This is the self-contained source snapshot corresponding to the final Windows build verified in GitHub Actions Run #186.

Exact included EXE SHA256:
`fae95e02554506033f3c98aee5c3883f2afbe6b5cbbc94deb9799ed055869d16`

This branch directly contains the final generated Go source, final web UI/runtime, MH icon resource, runtime tests, and the exact verified Run #186 EXE under `release/`.
No historical patch chain is required to inspect or build the source snapshot.


## DPI-adaptive Windows build
The current release is Per-Monitor V2 DPI aware so the embedded MH Analysis and WhatsApp views fill the host correctly across Windows display scaling levels. Verified runtime build: GitHub Actions DPI Run #3.
