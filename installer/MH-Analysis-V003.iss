#define MyAppName "MH Analysis"
#define MyAppVersion "V.03"
#define MyAppPublisher "Muhammad Hammad Shaukat"
#define MyAppExeName "MH Analysis.exe"

[Setup]
AppId={{8F2B90C0-0B17-4C4F-90D4-8170D5796170}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\MH Analysis
DefaultGroupName=MH Analysis
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir=..\dist\installer
OutputBaseFilename=MH Analysis V.03
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\web\mh-analysis.ico
UninstallDisplayName=MH Analysis
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\app\MH Analysis.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\MH Analysis"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\MH Analysis"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch MH Analysis"; Flags: nowait postinstall skipifsilent
