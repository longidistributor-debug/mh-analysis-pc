from pathlib import Path

MARK = "MH_SECURE_LICENSE_V801"

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

# The native shell stays visible so the login overlay can render in Analysis,
# but all other native tabs/actions remain locked until the server authorizes.
host = Path("chrome_host.go")
h = host.read_text(encoding="utf-8")
gate_marker = "MH_LICENSE_NATIVE_GATE_V801"
if gate_marker not in h:
    needle = '''\tcase chWMCommand:\n\t\tid := int(wParam & 0xffff)\n\t\tswitch id {\n'''
    replacement = '''\tcase chWMCommand:\n\t\tid := int(wParam & 0xffff)\n\t\t// MH_LICENSE_NATIVE_GATE_V801: Analysis remains reachable for login; every other native tab is fail-closed.\n\t\tif id != idAnalysis && !licEnsureAuthorized(false) {\n\t\t\tmessageBox(hostHWND, licAccessMessage(), "MH Analysis License", 0x30)\n\t\t\treturn 0\n\t\t}\n\t\tswitch id {\n'''
    if needle not in h:
        raise SystemExit("chrome_host.go native command anchor missing")
    h = h.replace(needle, replacement, 1)
host.write_text(h, encoding="utf-8")

for name in ["web/index.html", "web/records.html"]:
    p = Path(name)
    page = p.read_text(encoding="utf-8")
    if "/auth.css" not in page:
        if "</head>" not in page:
            raise SystemExit(f"{name} head anchor missing")
        page = page.replace("</head>", '<link rel="stylesheet" href="/auth.css" />\n</head>', 1)
    if "/auth.js" not in page:
        anchor = '<script src="/lightweight-charts.standalone.production.js"></script>'
        if anchor in page:
            page = page.replace(anchor, '<script src="/auth.js"></script>\n' + anchor, 1)
        elif "</body>" in page:
            page = page.replace("</body>", '<script src="/auth.js"></script>\n</body>', 1)
        else:
            raise SystemExit(f"{name} body anchor missing")
    p.write_text(page, encoding="utf-8")

print(MARK + " applied")
