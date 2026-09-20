from pathlib import Path

MARK = "MH_RECORDS_INLINE_V815"


def replace_func(src: str, name: str, next_name: str, body: str) -> str:
    start = src.find(f"func {name}(")
    if start < 0:
        raise SystemExit(f"missing function {name}")
    end = src.find(f"\nfunc {next_name}(", start)
    if end < 0:
        raise SystemExit(f"missing next function {next_name} after {name}")
    return src[:start] + body.rstrip() + "\n" + src[end:]

# -----------------------------------------------------------------------------
# Native shell: Records no longer depends on a second Chromium process.
# The working Analysis browser stays visible and app.js presents records.html in a
# same-origin full-surface iframe. This removes the blank Records-tab race entirely.
# -----------------------------------------------------------------------------
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    apply_body = r'''func chApplyDesiredBrowserView() {
	chMu.Lock()
	analysis := chAnalysisWnd
	whatsapp := chWhatsappWnd
	mt5 := chMT5Wnd
	chMu.Unlock()

	chViewMu.Lock()
	which := chDesiredView
	chViewMu.Unlock()

	// V81.5: Records (3) is rendered inside the already-authorized Analysis
	// Chromium surface. No second Chromium child is launched or required.
	chResizeChildren()
	chSetEmbeddedVisible(analysis, which == 1 || which == 3)
	chSetEmbeddedVisible(whatsapp, which == 2)
	chSetEmbeddedVisible(mt5, which == 4)
	// A legacy Records child, if one somehow exists from an older path, is never
	// shown in V81.5.
	chMu.Lock()
	legacyRecords := chRecordsWnd
	chMu.Unlock()
	chSetEmbeddedVisible(legacyRecords, false)
	chResizeChildren()
	if which == 3 {
		if analysis != 0 { chFocusEmbedded(analysis) }
	} else {
		chFocusDesiredEmbedded()
	}
}'''
    s = replace_func(s, "chApplyDesiredBrowserView", "chEnsureRecordsBrowser", apply_body)

    switch_body = r'''func chSwitchView(which int) {
	chViewMu.Lock()
	chDesiredView = which
	chViewMu.Unlock()

	// Preserve original Signal Link behavior: visible only in WhatsApp.
	if chSignalLinkBtn != 0 {
		if which == 2 {
			chShowWindow.Call(chSignalLinkBtn, chSWShow)
		} else {
			chShowWindow.Call(chSignalLinkBtn, chSWHide)
		}
	}

	// V81.5 Records is an in-page same-origin view. Never start a second browser.
	chApplyDesiredBrowserView()
	go func() {
		for _, d := range []time.Duration{40 * time.Millisecond, 140 * time.Millisecond, 360 * time.Millisecond} {
			time.Sleep(d)
			chMu.Lock(); stopping := chStopping; chMu.Unlock()
			if stopping { return }
			chResizeChildren()
		}
	}()
}'''
    s = replace_func(s, "chSwitchView", "chPopWhatsAppTask", switch_body)

    # Records WM_COMMAND can be synchronous again because it no longer launches
    # Chrome or performs slow cross-process startup work.
    s = s.replace('''\t\tcase idRecords:\n\t\t\tgo chSwitchView(3) // MH_RECORDS_VIEW_RECOVERY_V814: never block native UI thread\n''', '''\t\tcase idRecords:\n\t\t\tchSwitchView(3) // ''' + MARK + ''': instant in-page Records view\n''', 1)

    # Mark the generated host source for CI guards.
    s = s.replace('package main\n', 'package main\n\n// ' + MARK + '\n', 1)
    p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Local endpoint exposing only the current native tab number to the authorized
# Analysis page. No credentials or license material are exposed.
# -----------------------------------------------------------------------------
p = Path("main.go")
s = p.read_text(encoding="utf-8")
if "nativeViewHandlerV815" not in s:
    handler = r'''

// MH_RECORDS_INLINE_V815: bridge the native toolbar selection to the existing
// authorized Analysis Chromium page. Records itself still reads the same local
// /api/records-v2 lifecycle endpoints; only the presentation path changes.
func nativeViewHandlerV815(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	chViewMu.Lock()
	view := chDesiredView
	chViewMu.Unlock()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	_ = json.NewEncoder(w).Encode(map[string]int{"view": view})
}
'''
    anchor = '\nfunc main() {'
    if anchor not in s:
        raise SystemExit("main function anchor missing")
    s = s.replace(anchor, handler + anchor, 1)
    route_anchor = '\tmux := http.NewServeMux()\n'
    if route_anchor not in s:
        raise SystemExit("mux anchor missing")
    s = s.replace(route_anchor, route_anchor + '\tmux.HandleFunc("/api/native-view", nativeViewHandlerV815) // ' + MARK + '\n', 1)
    p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Web UI: use the already-working records.html inside the same Analysis Chromium.
# The overlay exists only after authoritative license authorization because app.js
# itself is auth-gated. Native toolbar remains outside Chromium and always visible.
# -----------------------------------------------------------------------------
p = Path("web/app.js")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    extra = r'''

// MH_RECORDS_INLINE_V815
(() => {
  const OVERLAY_ID = 'mhRecordsInlineV815';
  let overlay = null;
  let frame = null;
  let lastView = 0;
  let busy = false;

  function ensureRecordsOverlay() {
    if (overlay && frame) return;
    overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.setAttribute('aria-label', 'MH Analysis Records');
    overlay.style.cssText = [
      'position:fixed','inset:0','z-index:2147482000','background:#050b0d',
      'display:none','overflow:hidden','margin:0','padding:0'
    ].join(';');
    frame = document.createElement('iframe');
    frame.id = 'mhRecordsInlineFrameV815';
    frame.title = 'MH Analysis Records';
    frame.setAttribute('frameborder', '0');
    frame.style.cssText = 'width:100%;height:100%;border:0;display:block;background:#050b0d;';
    overlay.appendChild(frame);
    document.body.appendChild(overlay);
  }

  function setRecordsVisible(show) {
    ensureRecordsOverlay();
    if (show) {
      if (document.documentElement.dataset.mhLicenseAuthorized !== '1') return;
      if (!frame.dataset.loaded) {
        frame.src = '/records.html';
        frame.dataset.loaded = '1';
      }
      overlay.style.display = 'block';
      document.documentElement.dataset.mhNativeRecordsVisible = '1';
    } else {
      overlay.style.display = 'none';
      document.documentElement.dataset.mhNativeRecordsVisible = '0';
    }
  }

  async function syncNativeViewV815() {
    if (busy) return;
    busy = true;
    try {
      const r = await fetch('/api/native-view', { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      const view = Number(j?.view || 1);
      if (view !== lastView) {
        lastView = view;
        setRecordsVisible(view === 3);
      } else if (view === 3 && document.documentElement.dataset.mhNativeRecordsVisible !== '1') {
        setRecordsVisible(true);
      }
    } catch (_) {
      // Native shell remains authoritative; transient polling failure must never
      // disturb Analysis/WhatsApp/MT5.
    } finally {
      busy = false;
    }
  }

  window.addEventListener('mh-license-authorized', syncNativeViewV815);
  window.addEventListener('focus', syncNativeViewV815);
  setInterval(syncNativeViewV815, 140);
  syncNativeViewV815();
})();
'''
    s += extra
    p.write_text(s, encoding="utf-8")

print(MARK + ": Records uses authorized Analysis Chromium inline; no second-browser blank-view race")
