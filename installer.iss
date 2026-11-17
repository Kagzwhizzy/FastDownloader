; FastDownloader installer (Inno Setup 6)
#define AppName "FastDownloader"
#define AppVersion "1.1.0"
#define AppExe "FastDownloader.exe"

[Setup]
AppId={{6B2F7C2E-8D41-4E7A-9C3B-FA57D0C1E901}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Kagzwhizzy
AppPublisherURL=https://github.com/Kagzwhizzy/FastDownloader
AppSupportURL=https://github.com/Kagzwhizzy/FastDownloader/issues
AppUpdatesURL=https://github.com/Kagzwhizzy/FastDownloader/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=release
OutputBaseFilename=FastDownloader_Setup_{#AppVersion}
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start FastDownloader with &Windows (keeps the browser button working)"; GroupDescription: "Options:"

[Files]
Source: "dist\FastDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "extension\*"; DestDir: "{app}\Browser Extension"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installer_extension_guide.txt"; DestDir: "{app}"; DestName: "How to add the browser button.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Browser Extension folder"; Filename: "{app}\Browser Extension"
Name: "{group}\How to add the browser button"; Filename: "{app}\How to add the browser button.txt"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"" --tray"; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch FastDownloader now"; Flags: nowait postinstall skipifsilent
Filename: "{app}\How to add the browser button.txt"; Description: "Show how to add the browser button"; Flags: postinstall shellexec skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/im {#AppExe} /f"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
