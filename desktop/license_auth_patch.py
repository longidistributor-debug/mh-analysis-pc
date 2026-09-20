from pathlib import Path

MARK = "MH_SECURE_LICENSE_V800"

main = Path("main.go")
s = main.read_text(encoding="utf-8")
if "registerLicenseRoutes(mux)" not in s:
    needle = '\tmux := http.NewServeMux()\n'
    if needle not in s:
        raise SystemExit("main.go mux anchor missing")
    s = s.replace(needle, needle + '\tregisterLicenseRoutes(mux)\n', 1)

old = '\tserver = &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}'
new = '\tserver = &http.Server{Handler: licenseGate(mux), ReadHeaderTimeout: 10 * time.Second}'
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit("main.go server handler anchor missing")
main.write_text(s, encoding="utf-8")

for name in ["web/index.html", "web/records.html"]:
    p = Path(name)
    h = p.read_text(encoding="utf-8")
    if "/auth.css" not in h:
        if "</head>" not in h:
            raise SystemExit(f"{name} head anchor missing")
        h = h.replace("</head>", '<link rel="stylesheet" href="/auth.css" />\n</head>', 1)
    if "/auth.js" not in h:
        anchor = '<script src="/lightweight-charts.standalone.production.js"></script>'
        if anchor in h:
            h = h.replace(anchor, '<script src="/auth.js"></script>\n' + anchor, 1)
        elif "</body>" in h:
            h = h.replace("</body>", '<script src="/auth.js"></script>\n</body>', 1)
        else:
            raise SystemExit(f"{name} body anchor missing")
    p.write_text(h, encoding="utf-8")

print(MARK + " applied")
