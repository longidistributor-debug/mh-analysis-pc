from pathlib import Path

MARK = 'MH_LICENSE_INPUT_FOCUS_V802'


def rep(s, old, new, label):
    if new in s:
        return s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old, new, 1)


p = Path('chrome_host.go')
s = p.read_text(encoding='utf-8')
if MARK in s:
    print('PASS ' + MARK + ' already applied')
    raise SystemExit(0)

s = rep(
    s,
    '\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n',
    '\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n\tchSetFocus              = chUser32.NewProc("SetFocus") // ' + MARK + '\n\tchAttachThreadInput     = chUser32.NewProc("AttachThreadInput")\n',
    'focus procs',
)

s = rep(
    s,
    '\tchGetModuleHandle       = chKernel32.NewProc("GetModuleHandleW")\n',
    '\tchGetModuleHandle       = chKernel32.NewProc("GetModuleHandleW")\n\tchGetCurrentThreadID    = chKernel32.NewProc("GetCurrentThreadId")\n',
    'current thread proc',
)

s = rep(
    s,
    '\tchWMSize        = 0x0005\n',
    '\tchWMSize        = 0x0005\n\tchWMSetFocus    = 0x0007 // ' + MARK + '\n',
    'setfocus constant',
)

helper = r'''
// MH_LICENSE_INPUT_FOCUS_V802
// Chromium is re-parented into the native shell from a different process/thread.
// Explicitly bridge input queues while assigning keyboard focus so HTML login
// text boxes receive keystrokes reliably after the host is activated/shown.
func chFocusEmbedded(hwnd uintptr) {
	if hwnd == 0 { return }
	if hostHWND != 0 { chSetForegroundWindow.Call(hostHWND) }
	targetThread, _, _ := chGetWindowThreadPID.Call(hwnd, 0)
	currentThread, _, _ := chGetCurrentThreadID.Call()
	if targetThread != 0 && currentThread != 0 && targetThread != currentThread {
		chAttachThreadInput.Call(currentThread, targetThread, 1)
		chSetFocus.Call(hwnd)
		chAttachThreadInput.Call(currentThread, targetThread, 0)
		return
	}
	chSetFocus.Call(hwnd)
}

func chFocusDesiredEmbedded() {
	chViewMu.Lock()
	which := chDesiredView
	chViewMu.Unlock()
	chMu.Lock()
	analysis, whatsapp, records, mt5 := chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd
	chMu.Unlock()
	var target uintptr
	switch which {
	case 2: target = whatsapp
	case 3: target = records
	case 4: target = mt5
	default: target = analysis
	}
	if target != 0 { chFocusEmbedded(target) }
}
'''

s = rep(s, '\nfunc chResizeChildren() {', '\n' + helper + '\nfunc chResizeChildren() {', 'focus helpers')

# When the Analysis child becomes visible, immediately restore keyboard focus.
old_analysis = 'if analysis != 0 { chSetEmbeddedVisible(analysis,true) }'
new_analysis = 'if analysis != 0 { chSetEmbeddedVisible(analysis,true); chFocusEmbedded(analysis) }'
if old_analysis in s:
    s = s.replace(old_analysis, new_analysis)
elif new_analysis not in s:
    # Expanded formatting fallback.
    old_analysis2 = '''if analysis != 0 {
		chSetEmbeddedVisible(analysis,true)
	}'''
    new_analysis2 = '''if analysis != 0 {
		chSetEmbeddedVisible(analysis,true)
		chFocusEmbedded(analysis)
	}'''
    if old_analysis2 not in s:
        raise SystemExit('analysis visibility focus anchor missing')
    s = s.replace(old_analysis2, new_analysis2, 1)

# Host activation/focus is forwarded to whichever embedded tab is active.
needle = '''\tswitch msg {\n\tcase chWMSize:\n'''
replacement = '''\tswitch msg {\n\tcase chWMSetFocus:\n\t\tgo func(){ time.Sleep(20*time.Millisecond); chFocusDesiredEmbedded() }()\n\t\treturn 0\n\tcase chWMSize:\n'''
s = rep(s, needle, replacement, 'host setfocus handler')

p.write_text(s, encoding='utf-8')
print('PASS ' + MARK + ': native host forwards keyboard focus to embedded Chromium login')
