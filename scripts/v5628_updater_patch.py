from pathlib import Path
import re

root = Path('.')
up = root / 'updater.go'
s = up.read_text(encoding='utf-8')

s = s.replace('const mhPublicVersionV001 = "V.56.27"', 'const mhPublicVersionV001 = "V.56.28"', 1)

pat = re.compile(r'func mhFetchManifestV001\(\) \(mhUpdateManifestV001, error\) \{.*?\n\}\nfunc mhWriteJSONV001', re.S)
new = r'''func mhFetchManifestFromURLV002(u string) (mhUpdateManifestV001, error) {
	var m mhUpdateManifestV001
	u = strings.TrimSpace(u)
	if u == "" {
		return m, errors.New("empty update manifest url")
	}
	sep := "?"
	if strings.Contains(u, "?") {
		sep = "&"
	}
	req, err := http.NewRequest(http.MethodGet, u+sep+"mh="+strconv.FormatInt(time.Now().UnixNano(), 10), nil)
	if err != nil {
		return m, err
	}
	req.Header.Set("Cache-Control", "no-cache, no-store, max-age=0")
	req.Header.Set("Pragma", "no-cache")
	req.Header.Set("Expires", "0")
	req.Header.Set("User-Agent", "MH-Analysis-"+mhPublicVersionV001)
	resp, err := (&http.Client{Timeout: 15 * time.Second}).Do(req)
	if err != nil {
		return m, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return m, fmt.Errorf("update service returned %d", resp.StatusCode)
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
	if err != nil {
		return m, err
	}
	raw = bytes.TrimPrefix(raw, []byte{0xEF, 0xBB, 0xBF})
	raw = bytes.TrimSpace(raw)
	if err := json.Unmarshal(raw, &m); err != nil {
		return m, fmt.Errorf("invalid update manifest json: %w", err)
	}
	m.Version = strings.TrimSpace(m.Version)
	m.DownloadURL = strings.TrimSpace(m.DownloadURL)
	m.SHA256 = strings.ToLower(strings.TrimSpace(m.SHA256))
	if m.Version == "" || m.DownloadURL == "" || len(m.SHA256) != 64 {
		return m, errors.New("invalid update manifest")
	}
	if !strings.HasPrefix(strings.ToLower(m.DownloadURL), "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/") &&
		!strings.HasPrefix(strings.ToLower(m.DownloadURL), "https://github.com/longidistributor-debug/mh-analysis-pc/releases/download/") {
		return m, errors.New("untrusted update source")
	}
	return m, nil
}

func mhFetchManifestV001() (mhUpdateManifestV001, error) {
	// V.56.28: canonical production manifest is always checked. A stale
	// MH_UPDATE_MANIFEST_URL override can no longer hide a newer production build.
	urls := []string{mhUpdateManifestURLV001}
	override := strings.TrimSpace(os.Getenv("MH_UPDATE_MANIFEST_URL"))
	if override != "" && !strings.EqualFold(override, mhUpdateManifestURLV001) {
		urls = append(urls, override)
	}
	var best mhUpdateManifestV001
	have := false
	errs := make([]string, 0, len(urls))
	for _, u := range urls {
		m, err := mhFetchManifestFromURLV002(u)
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		if !have || mhVersionNumberV001(m.Version) > mhVersionNumberV001(best.Version) {
			best = m
			have = true
		}
	}
	if have {
		return best, nil
	}
	return mhUpdateManifestV001{}, fmt.Errorf("all update manifests failed: %s", strings.Join(errs, "; "))
}
func mhWriteJSONV001'''

s2, n = pat.subn(new, s, count=1)
if n != 1:
    raise SystemExit('mhFetchManifestV001 replacement failed')
s = s2

old = 'required := m.Mandatory && !binaryCurrent && mhNewerVersionV001(m.Version, mhPublicVersionV001)'
new_req = 'required := m.Mandatory && !binaryCurrent && mhVersionNumberV001(m.Version) >= mhVersionNumberV001(mhPublicVersionV001)'
if old not in s:
    raise SystemExit('required condition anchor missing')
s = s.replace(old, new_req, 1)

old = 'if mhManifestMatchesCurrentExecutableV001(m) || !m.Mandatory || !mhNewerVersionV001(m.Version, mhPublicVersionV001) {'
new_start = 'if mhManifestMatchesCurrentExecutableV001(m) || !m.Mandatory || mhVersionNumberV001(m.Version) < mhVersionNumberV001(mhPublicVersionV001) {'
if old not in s:
    raise SystemExit('start condition anchor missing')
s = s.replace(old, new_start, 1)

old = 'req, err := http.NewRequest(http.MethodGet, m.DownloadURL, nil)'
new_dl = '''u := m.DownloadURL
	sep := "?"
	if strings.Contains(u, "?") {
		sep = "&"
	}
	req, err := http.NewRequest(http.MethodGet, u+sep+"mhbin="+strconv.FormatInt(time.Now().UnixNano(), 10), nil)'''
if old not in s:
    raise SystemExit('download request anchor missing')
s = s.replace(old, new_dl, 1)

old = 'req.Header.Set("Cache-Control", "no-cache")\n\treq.Header.Set("User-Agent", "MH-Analysis-Updater-"+mhPublicVersionV001)'
new_headers = 'req.Header.Set("Cache-Control", "no-cache, no-store, max-age=0")\n\treq.Header.Set("Pragma", "no-cache")\n\treq.Header.Set("Expires", "0")\n\treq.Header.Set("User-Agent", "MH-Analysis-Updater-"+mhPublicVersionV001)'
if old not in s:
    raise SystemExit('download header anchor missing')
s = s.replace(old, new_headers, 1)

up.write_text(s, encoding='utf-8', newline='\n')

(root / 'VERSION').write_text('V.56.28\n', encoding='ascii')
for path, oldv, newv in [
    ('license_auth.go', 'const licAppVersion = "V.56.27"', 'const licAppVersion = "V.56.28"'),
    ('webview2_host.go', 'Version: V.56.27', 'Version: V.56.28'),
    ('web/index.html', 'id="mhUpdateVersionV001">V.56.27<', 'id="mhUpdateVersionV001">V.56.28<'),
]:
    p = root / path
    x = p.read_text(encoding='utf-8')
    if oldv not in x:
        raise SystemExit(f'version anchor missing: {path}')
    p.write_text(x.replace(oldv, newv, 1), encoding='utf-8', newline='\n')

# Keep updater checks frequent and explicitly bypass local HTTP cache.
js = root / 'web/update-v001.js'
x = js.read_text(encoding='utf-8')
x = x.replace("fetch('/api/update/status',{cache:'no-store'})", "fetch('/api/update/status?mhui='+Date.now(),{cache:'no-store'})")
x = x.replace("fetch('/api/update/start',{method:'POST',cache:'no-store'})", "fetch('/api/update/start?mhui='+Date.now(),{method:'POST',cache:'no-store'})")
x = x.replace('setInterval(()=>checkVersion(true),60000);', 'setInterval(()=>checkVersion(true),30000);')
js.write_text(x, encoding='utf-8', newline='\n')

print('V.56.28 updater hardening patch applied')
