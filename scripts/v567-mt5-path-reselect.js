const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,needle,label){if(!s.includes(needle))throw new Error(label+' marker not found')}

// V56.7: the chooser accepts only the real MT5 installation executable path.
// Windows shortcut files are deliberately not dereferenced or accepted.
{
  const p='mt5_selector_v566.go'; let s=read(p);

  if(!s.includes('wmMT5ReselectV567')){
    const m='\twmMT5SelectedV566 = 0x8F5A\n';
    must(s,m,'selector message const');
    s=s.replace(m,m+'\twmMT5ReselectV567 = 0x8F5B\n');
  }

  const validate=`\tif p == "" { return "", errors.New("Select the MT5 terminal executable first.") }\n\tbase := strings.ToLower(filepath.Base(p))\n`;
  must(s,validate,'MT5 path validation');
  s=s.replace(validate,`\tif p == "" { return "", errors.New("Select the MT5 terminal executable first.") }\n\tif strings.EqualFold(filepath.Ext(p), ".lnk") {\n\t\treturn "", errors.New("Do not select an MT5 shortcut. Open the broker MT5 installation folder and select terminal64.exe (or terminal.exe).")\n\t}\n\tbase := strings.ToLower(filepath.Base(p))\n`);

  const save=`func v566SaveMT5Path(p string) error {\n\tp, err := v566ValidateMT5Path(p)\n\tif err != nil { return err }\n\tsettingsMu.Lock()\n`;
  must(s,save,'MT5 save path');
  s=s.replace(save,`func v566SaveMT5Path(p string) error {\n\tp, err := v566ValidateMT5Path(p)\n\tif err != nil { return err }\n\toldPath := getSettings().MT5Path\n\tif oldPath != "" && !v566SamePath(oldPath, p) { v567ReleaseCurrentMT5ForNewPath(p) }\n\tsettingsMu.Lock()\n`);

  const filter='\tfilter := v566UTF16Multi("MetaTrader 5 Terminal (*.exe)\\x00*.exe\\x00All Files (*.*)\\x00*.*\\x00")\n';
  must(s,filter,'MT5 file filter');
  s=s.replace(filter,'\tfilter := v566UTF16Multi("MT5 Terminal (terminal64.exe;terminal.exe)\\x00terminal64.exe;terminal.exe\\x00")\n');

  const title='\ttitle, _ := syscall.UTF16PtrFromString("Select the exact MT5 terminal executable")\n';
  must(s,title,'MT5 chooser title');
  s=s.replace(title,'\ttitle, _ := syscall.UTF16PtrFromString("Select MT5 installation terminal - not a shortcut")\n');

  const beforeOFN='\tdefExt, _ := syscall.UTF16PtrFromString("exe")\n\tofn := v566OpenFileName{\n';
  must(s,beforeOFN,'MT5 chooser options');
  s=s.replace(beforeOFN,`\tdefExt, _ := syscall.UTF16PtrFromString("exe")\n\tvar initialDir *uint16\n\tif current != "" {\n\t\tif d := filepath.Dir(current); d != "" { initialDir, _ = syscall.UTF16PtrFromString(d) }\n\t} else if d := strings.TrimSpace(os.Getenv("PROGRAMFILES")); d != "" {\n\t\tinitialDir, _ = syscall.UTF16PtrFromString(d)\n\t}\n\tofn := v566OpenFileName{\n`);

  const owner='\t\tHwndOwner: owner,\n\t\tLpstrFilter: &filter[0],\n';
  must(s,owner,'MT5 chooser owner');
  s=s.replace(owner,'\t\tHwndOwner: owner,\n\t\tLpstrFilter: &filter[0],\n\t\tLpstrInitialDir: initialDir,\n');

  const flags='\t\tFlags: 0x00001000 | 0x00000800 | 0x00080000 | 0x00000008,\n';
  must(s,flags,'MT5 chooser flags');
  s=s.replace(flags,'\t\t// FILEMUSTEXIST | PATHMUSTEXIST | EXPLORER | NOCHANGEDIR | NODEREFERENCELINKS\n\t\tFlags: 0x00001000 | 0x00000800 | 0x00080000 | 0x00000008 | 0x00100000,\n');

  const result=`\tp := syscall.UTF16ToString(buf)\n\tif _, err := v566ValidateMT5Path(p); err != nil {\n`;
  must(s,result,'MT5 chooser result');
  s=s.replace(result,`\tp := syscall.UTF16ToString(buf)\n\tif strings.EqualFold(filepath.Ext(strings.TrimSpace(p)), ".lnk") {\n\t\tmessageBox(owner, "A shortcut cannot be used here. Open the actual MT5 installation folder and select terminal64.exe (or terminal.exe).", "MH MT5", 0x10)\n\t\treturn "", false\n\t}\n\tif _, err := v566ValidateMT5Path(p); err != nil {\n`);

  s=s.replace('const dlgH int32 = 270','const dlgH int32 = 305');
  s=s.replace('Select the exact MT5 terminal that MH Analysis may embed.','Select the actual broker MT5 installation file: terminal64.exe (or terminal.exe).');
  s=s.replace('All other MT5 terminals will remain independent and will not be hidden, minimized, closed, or re-parented.','Do not select a Desktop/Start Menu shortcut (.lnk). All other MT5 terminals remain completely independent.');
  s=s.replace('chWSChild|chWSVisible|chWSBorder|v566ESReadOnly, 22, 82, 700, 34','chWSChild|chWSVisible|chWSBorder|v566ESReadOnly, 22, 92, 700, 34');
  s=s.replace('chWstr("SELECT EXE")','chWstr("SELECT MT5 PATH")');
  s=s.replace('chWSChild|chWSVisible|chWSTabStop, 22, 138, 180, 38','chWSChild|chWSVisible|chWSTabStop, 22, 150, 180, 38');
  s=s.replace('chWSChild|chWSVisible|chWSTabStop, 214, 138, 180, 38','chWSChild|chWSVisible|chWSTabStop, 214, 150, 180, 38');
  s=s.replace('chWSChild|chWSVisible|chWSTabStop, 406, 138, 180, 38','chWSChild|chWSVisible|chWSTabStop, 406, 150, 180, 38');

  const restore='func v566RestoreStandaloneMT5(hwnd uintptr) {';
  must(s,restore,'restore standalone function');
  if(!s.includes('func v567HandleMT5Button()')){
    const helpers=`// V56.7: when changing the selected terminal, detach only the previously\n// selected embedded MT5. It becomes a normal standalone terminal; unrelated\n// MT5 installations are never enumerated or touched.\nfunc v567ReleaseCurrentMT5ForNewPath(newPath string) {\n\tchMu.Lock()\n\thwnd := chMT5Wnd\n\tcmd := chMT5Cmd\n\tchMu.Unlock()\n\tif hwnd == 0 || v566WindowMatchesPath(hwnd, newPath) { return }\n\tv566RestoreStandaloneMT5(hwnd)\n\tchMu.Lock()\n\tif chMT5Wnd == hwnd { chMT5Wnd = 0 }\n\tif chMT5Cmd == cmd { chMT5Cmd = nil }\n\tchMu.Unlock()\n}\n\n// Clicking MH MT5 while already viewing the embedded terminal opens the\n// selector again, so a valid-but-wrong terminal can be changed without restart.\nfunc v567HandleMT5Button() {\n\tchViewMu.Lock(); desired := chDesiredView; chViewMu.Unlock()\n\tchMu.Lock(); hwnd := chMT5Wnd; chMu.Unlock()\n\tif v566MT5SelectionConfirmed && desired == 4 && hwnd != 0 {\n\t\tv566ShowMT5Selector()\n\t\treturn\n\t}\n\twv2ShowMT5()\n}\n\n`;
    s=s.replace(restore,helpers+restore);
  }

  write(p,s);
}

// V56.7: if a chosen executable cannot launch/embed, return to the themed MT5
// selector automatically. Also allow re-selection by clicking MH MT5 again while
// the embedded MT5 view is already active.
{
  const p='webview2_host.go'; let s=read(p);

  const button='case idMT5:wv2ShowMT5();';
  must(s,button,'MT5 button handler');
  s=s.replace(button,'case idMT5:v567HandleMT5Button();');

  const err='if err!=nil{messageBox(hostHWND,err.Error(),"MH MT5",0x10);postMessage(hostHWND,wmSwitchAnalysis,0,0);return};';
  must(s,err,'MT5 launch error handler');
  s=s.replace(err,'if err!=nil{v566MT5SelectionConfirmed=false;messageBox(hostHWND,err.Error()+"\\n\\nSelect the actual terminal64.exe/terminal.exe from the broker MT5 installation folder. Desktop shortcuts are not accepted.","MH MT5",0x10);postMessage(hostHWND,wmSwitchAnalysis,0,0);postMessage(hostHWND,wmMT5ReselectV567,0,0);return};');

  const msg='case wmMT5SelectedV566:wv2ShowMT5();return 0;case wmWhatsAppNativeEnterV5414:';
  must(s,msg,'MT5 selected message hook');
  s=s.replace(msg,'case wmMT5SelectedV566:wv2ShowMT5();return 0;case wmMT5ReselectV567:v566ShowMT5Selector();return 0;case wmWhatsAppNativeEnterV5414:');

  write(p,s);
}

console.log('V56.7 MT5 path/reselect patch applied');
