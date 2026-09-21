#define MyAppName "MH Analysis"
#ifndef MyAppVersion
  #define MyAppVersion "V.01"
#endif
#define MyAppPublisher "Muhammad Hammad Shaukat"
#define MyAppExeName "MH Analysis.exe"
#ifndef MySourceExe
  #define MySourceExe "..\MH Analysis.exe"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist-installer"
#endif

[Setup]
; IMPORTANT: this AppId is intentionally unchanged from the existing MH Analysis
; installer so every future setup updates the SAME installed product.
AppId={{D44F9625-59E0-4F6A-9A0E-AECF7DF81B16}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\MH Analysis
DefaultGroupName=MH Analysis
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename=MH-Analysis-Setup-V.01
SetupIconFile=..\web\mh-analysis.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
VersionInfoVersion=0.1.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=MH Analysis Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
; ignoreversion is deliberate: a public version reset to V.01 must still replace
; the previously installed EXE when this same-product installer is run.
Source: "{#MySourceExe}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
; Same names and same targets mean an update refreshes the existing shortcuts;
; it does not create a second MH Analysis shortcut/icon.
Name: "{autoprograms}\MH Analysis"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\MH Analysis"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\MH Analysis"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\MH Analysis"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MH Analysis"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
