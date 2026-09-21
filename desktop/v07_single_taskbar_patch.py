from pathlib import Path
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
# Prevent child Chromium app windows from ever becoming taskbar app windows before embedding.
s=s.replace('"--window-position=-32000,-32000",\n\t\t"--window-size=1280,820",', '"--window-position=-32000,-32000",\n\t\t"--window-size=1,1",\n\t\t"--start-minimized",')
# Keep the native host hidden until Analysis is embedded; this removes the blank/flicker phase.
s=s.replace('\tchShowWindow.Call(hostHWND, chSWMaximize)\n\tchUpdateWindow.Call(hostHWND)\n\n\t// Start browsers asynchronously', '\t// V.07: keep host hidden until the Analysis child is fully embedded.\n\t// This prevents startup flicker and transient child taskbar icons.\n\n\t// Start browsers asynchronously')
s=s.replace('\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t}()\n\n\tgo func() {\n\t\ttime.Sleep(150 * time.Millisecond)\n\t\tcmd, wnd, err := chLaunchBrowser("WhatsAppProfile"', '\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t\tchShowWindow.Call(hostHWND, chSWMaximize)\n\t\tchUpdateWindow.Call(hostHWND)\n\t}()\n\n\t// V.07: WhatsApp is delayed until after the primary embedded view is stable.\n\tgo func() {\n\t\ttime.Sleep(1200 * time.Millisecond)\n\t\tcmd, wnd, err := chLaunchBrowser("WhatsAppProfile"', 1)
# Hide children before destroying host so shutdown never exposes their taskbar windows.
s=s.replace('\tcase chWMClose:\n\t\tchDestroyWindow.Call(hwnd)', '\tcase chWMClose:\n\t\tchMu.Lock()\n\t\tfor _, w := range []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd} { if w != 0 { chShowWindow.Call(w, chSWHide) } }\n\t\tchMu.Unlock()\n\t\tchDestroyWindow.Call(hwnd)')
p.write_text(s,encoding='utf-8')

# Promote real source version to V.07.
p=Path('updater.go'); s=p.read_text(encoding='utf-8').replace('mhPublicVersionV001 = "V.06"','mhPublicVersionV001 = "V.07"'); p.write_text(s,encoding='utf-8')
p=Path('VERSION'); p.write_text('V.07\n',encoding='utf-8')
p=Path('web/index.html'); s=p.read_text(encoding='utf-8').replace('id="mhUpdateVersionV001">V.06<','id="mhUpdateVersionV001">V.07<'); p.write_text(s,encoding='utf-8')
