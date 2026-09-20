from pathlib import Path

MARK = "MH_V816_BRANDING_SECURITY"
COPY = "MH ANALYSIS BY: Muhammad Hammad Shaukat - © 2026. All Rights Reserved."

# -----------------------------------------------------------------------------
# Records footer + branded reset confirmation dialog.
# -----------------------------------------------------------------------------
p = Path("web/records.html")
s = p.read_text(encoding="utf-8")
old = '<span>Outcomes come from your attached MT5 EA trade_events.jsonl • no FCS history is used for Records verification.</span>'
new = '<span class="recordsCopyrightV816">' + COPY + '</span>'
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit("records footer anchor missing")
p.write_text(s, encoding="utf-8")

p = Path("web/records.js")
s = p.read_text(encoding="utf-8")
helper = r'''

// MH_V816_BRANDING_SECURITY: branded, in-app reset confirmation. This replaces
// Chromium's browser-owned confirm() popup, so the Records reset stays visually
// consistent with MH Analysis and never exposes a 127.0.0.1 browser alert.
function mhConfirmResetV816(label){
  return new Promise(resolve=>{
    let wrap=document.getElementById('mhResetModalV816');
    if(wrap)wrap.remove();
    wrap=document.createElement('div');
    wrap.id='mhResetModalV816';
    wrap.className='mhResetOverlayV816';
    wrap.innerHTML=`<div class="mhResetCardV816" role="dialog" aria-modal="true" aria-label="Reset Records">
      <div class="mhResetHeadV816"><img src="/mh-logo.png" alt="MH"><div><b>RESET RECORDS</b><span>MH Analysis</span></div></div>
      <div class="mhResetBodyV816">
        <div class="mhResetQuestionV816">Delete saved Records for <strong>${esc(label)}</strong>?</div>
        <div class="mhResetNoteV816">This resets MH Analysis records only. It does not delete MT5 account history.</div>
      </div>
      <div class="mhResetActionsV816"><button type="button" class="cancel">CANCEL</button><button type="button" class="confirm">RESET</button></div>
    </div>`;
    const finish=v=>{document.removeEventListener('keydown',onKey);wrap.remove();resolve(v)};
    const onKey=e=>{if(e.key==='Escape')finish(false)};
    wrap.querySelector('.cancel').addEventListener('click',()=>finish(false));
    wrap.querySelector('.confirm').addEventListener('click',()=>finish(true));
    wrap.addEventListener('click',e=>{if(e.target===wrap)finish(false)});
    document.addEventListener('keydown',onKey);
    document.body.appendChild(wrap);
    wrap.querySelector('.confirm').focus();
  });
}
'''
anchor = 'async function resetSelectedRecords(){\n'
if 'function mhConfirmResetV816' not in s:
    if anchor not in s:
        raise SystemExit("records reset function anchor missing")
    s = s.replace(anchor, helper + anchor, 1)
old_confirm = "  if(!confirm(`Delete saved Records for ${label}?\\n\\nThis resets MH Analysis records only. It does not delete MT5 account history.`))return;"
new_confirm = "  if(!(await mhConfirmResetV816(label)))return;"
if old_confirm in s:
    s = s.replace(old_confirm, new_confirm, 1)
elif new_confirm not in s:
    raise SystemExit("records browser confirm anchor missing")
p.write_text(s, encoding="utf-8")

p = Path("web/records.css")
s = p.read_text(encoding="utf-8")
css = r'''

/* MH_V816_BRANDING_SECURITY */
.recordsFooter{flex-direction:column;align-items:center!important;justify-content:center!important;text-align:center!important;color:#fff!important;padding-top:14px!important}
.recordsFooter .recordsCopyrightV816{color:#fff!important;font-size:9px;font-weight:700;letter-spacing:.01em}
.recordsFooter #lastRefresh{color:#6e8981;font-size:8px}
.mhResetOverlayV816{position:fixed;inset:0;z-index:2147483000;background:rgba(0,0,0,.72);display:grid;place-items:center;padding:22px}
.mhResetCardV816{width:min(650px,94vw);background:#071317;border:1px solid #31515a;box-shadow:0 24px 70px #000b;border-radius:0;color:#eef8f4;overflow:hidden;font-family:"Segoe UI",Arial,sans-serif}
.mhResetHeadV816{height:58px;display:flex;align-items:center;gap:11px;padding:10px 18px;border-bottom:1px solid #163a36;background:#08171b}
.mhResetHeadV816 img{width:30px;height:30px;object-fit:cover;border-radius:5px;box-shadow:0 0 0 1px #a27b16}
.mhResetHeadV816 b{display:block;color:#fff;font-size:13px;letter-spacing:.04em}.mhResetHeadV816 span{display:block;color:#8ba9a0;font-size:9px;margin-top:2px}
.mhResetBodyV816{padding:22px 20px 18px}.mhResetQuestionV816{font-size:12px;color:#fff;line-height:1.5}.mhResetQuestionV816 strong{color:#ffc857}.mhResetNoteV816{font-size:10px;line-height:1.55;color:#a7bbb5;margin-top:10px}
.mhResetActionsV816{display:flex;gap:10px;padding:0 20px 20px}.mhResetActionsV816 button{height:38px;min-width:150px;border:1px solid #536269;background:#f0f0f0;color:#111;font-size:10px;font-weight:800;cursor:pointer}.mhResetActionsV816 .confirm{border-color:#7a333c;background:#381419;color:#ff9ca5}.mhResetActionsV816 button:focus{outline:2px solid #20f59a;outline-offset:1px}
'''
if MARK not in s:
    s += css
p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Main MH Analysis-only footer. It lives inside index.html/appShell, so it never
# appears in WhatsApp, MT5 or the Records iframe overlay.
# -----------------------------------------------------------------------------
p = Path("web/index.html")
s = p.read_text(encoding="utf-8")
footer = '  <footer class="mhMainCopyrightV816">' + COPY + '</footer>\n'
if 'mhMainCopyrightV816' not in s:
    anchor = '  </main>\n</div>\n'
    if anchor not in s:
        raise SystemExit("index main/appShell anchor missing")
    s = s.replace(anchor, '  </main>\n' + footer + '</div>\n', 1)
p.write_text(s, encoding="utf-8")

p = Path("web/styles.css")
s = p.read_text(encoding="utf-8")
main_css = r'''

/* MH_V816_BRANDING_SECURITY: MH Analysis-only copyright footer */
.mhMainCopyrightV816{width:100%;text-align:center;color:#fff;font-size:10px;font-weight:650;letter-spacing:.01em;padding:15px 8px 8px;margin-top:8px;border-top:1px solid rgba(255,255,255,.06)}
'''
if 'mhMainCopyrightV816' not in s:
    s += main_css
p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Native window branding + Windows capture exclusion.
# API Access Key and WhatsApp Signal Link are top-level windows in this EXE
# process. A small process-window sweep applies the MH icon to their title bars and
# WDA_EXCLUDEFROMCAPTURE to the host/dialogs. Windows may reject the affinity on
# unsupported OS versions; failure is intentionally non-fatal.
# -----------------------------------------------------------------------------
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    proc_anchor = '\tchSetWindowTheme        = chUxTheme.NewProc("SetWindowTheme")\n'
    proc_new = proc_anchor + '\tchSendMessageV816       = chUser32.NewProc("SendMessageW") // '+MARK+'\n\tchSetWindowDisplayAffinityV816 = chUser32.NewProc("SetWindowDisplayAffinity")\n'
    if proc_anchor not in s:
        raise SystemExit("native proc anchor missing")
    s = s.replace(proc_anchor, proc_new, 1)

    const_anchor = '\tchIDCArrow      = 32512\n'
    const_new = const_anchor + '\tchWMSetIconV816 = 0x0080\n\tchIconSmallV816 = 0\n\tchIconBigV816 = 1\n\tchWDAExcludeFromCaptureV816 = 0x00000011\n'
    if const_anchor not in s:
        raise SystemExit("native const anchor missing")
    s = s.replace(const_anchor, const_new, 1)

    helper_native = r'''

// MH_V816_BRANDING_SECURITY
func chProtectEnumWindowV816(hwnd, lparam uintptr) uintptr {
	var pid uint32
	chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
	if pid != uint32(os.Getpid()) { return 1 }
	inst, _, _ := chGetModuleHandle.Call(0)
	icon, _, _ := chLoadIcon.Call(inst, 1)
	if icon != 0 {
		chSendMessageV816.Call(hwnd, chWMSetIconV816, chIconBigV816, icon)
		chSendMessageV816.Call(hwnd, chWMSetIconV816, chIconSmallV816, icon)
	}
	// Best-effort Windows capture exclusion for the EXE host and its native
	// settings dialogs. This blocks standard Windows capture paths on supported
	// builds without crashing older systems if the call is unavailable/denied.
	chSetWindowDisplayAffinityV816.Call(hwnd, chWDAExcludeFromCaptureV816)
	return 1
}

var chProtectEnumCbV816 = syscall.NewCallback(chProtectEnumWindowV816)

func chBrandAndProtectNativeWindowsV816() {
	chEnumWindows.Call(chProtectEnumCbV816, 0)
}

func chProtectionLoopV816() {
	for {
		chMu.Lock(); stopping := chStopping; chMu.Unlock()
		if stopping { return }
		chBrandAndProtectNativeWindowsV816()
		time.Sleep(250 * time.Millisecond)
	}
}
'''
    anchor = '\nfunc chWstr(s string) *uint16 {'
    if anchor not in s:
        raise SystemExit("native helper anchor missing")
    s = s.replace(anchor, helper_native + anchor, 1)

    # Start after all native shell controls have been created, immediately before
    # the host message loop begins. The sweep then also catches dialogs created later.
    loop_anchor = '\tvar m chMsg\n'
    loop_new = '\tchBrandAndProtectNativeWindowsV816() // '+MARK+'\n\tgo chProtectionLoopV816()\n\n' + loop_anchor
    if loop_anchor not in s:
        raise SystemExit("native message-loop anchor missing")
    s = s.replace(loop_anchor, loop_new, 1)

    s = s.replace('package main\n', 'package main\n\n// '+MARK+'\n', 1)
    p.write_text(s, encoding="utf-8")

print(MARK + ": records copyright + branded reset + titlebar MH icons + MH-only footer + Windows capture exclusion")
