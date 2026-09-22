#define MyAppName "MH Analysis"
#define MyAppVersion "27.0"
#define MyAppPublisher "Muhammad Hammad Shaukat"
#define MyAppExeName "MH Analysis.exe"
#ifndef MySourceExe
  #define MySourceExe "..\dist\MH Analysis.exe"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist"
#endif

[Setup]
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
OutputBaseFilename=MH-Analysis-Setup-V27
SetupIconFile=..\web\mh-analysis.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
VersionInfoVersion=27.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=MH Analysis Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
Source: "{#MySourceExe}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MH Analysis"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\MH Analysis"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\MH Analysis"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\MH Analysis"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MH Analysis"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
