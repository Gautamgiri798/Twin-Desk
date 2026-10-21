; DualDesk — Inno Setup Script
; Production Windows Standalone Installer & Uninstaller Specification
; Bundles DualDesk application binaries, native IDD driver manifests, and firewall configurator

#define MyAppName "DualDesk"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "DualDesk Open Source Project"
#define MyAppURL "https://github.com/Gautamgiri798/Twin-Desk"
#define MyAppExeName "DualDesk.exe"

[Setup]
AppId={{E68F91B4-325A-4B6A-B68C-083637F5D1A2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\README.md
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=DualDesk_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Launch DualDesk automatically on Windows startup"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
; Main application binaries from staging directory
Source: "..\dist\dualdesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Native IDD driver package
Source: "..\native\idd_driver\IddDriver.inf"; DestDir: "{app}\driver"; Flags: ignoreversion
Source: "..\native\idd_driver\*.cpp"; DestDir: "{app}\driver\src"; Flags: ignoreversion
Source: "..\native\idd_driver\*.h"; DestDir: "{app}\driver\src"; Flags: ignoreversion
; Maintenance & Firewall scripts
Source: "..\scripts\configure_firewall.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\build_driver.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autostartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
; Automatically configure inbound firewall rules for UDP 53891, TCP 53892, TCP 53893
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File ""{app}\scripts\configure_firewall.ps1"""; StatusMsg: "Configuring Windows Firewall rules for LAN discovery and media streaming..."; Flags: runhidden
; Post-install launch option
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Remove DualDesk Windows Firewall rules cleanly on uninstall
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File ""{app}\scripts\configure_firewall.ps1"" -Remove"; Flags: runhidden
; Remove user-mode virtual display devices if registered
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -Command ""if (Get-Command devcon.exe -ErrorAction SilentlyContinue) { devcon.exe remove Root\DualDeskDisplay }"""; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\*.db"
Type: files; Name: "{app}\*.db-journal"
Type: files; Name: "{app}\*.log"

[Code]
// Ensures any running instance of DualDesk is gracefully terminated before upgrade/install
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM DualDesk.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM DualDesk.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
