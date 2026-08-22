; Inno Setup POC — SQE DailyWork (experimental, unsigned)
; Build: iscc installer\sqe_dailywork.iss
; Requires prior: scripts\build_windows.ps1

#define RepoRoot ".."
#define DistDir RepoRoot + "\dist\SQE_DailyWork"
#define OutputDir RepoRoot + "\dist"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=SQE DailyWork
AppVersion=1.1.0
AppPublisher=Mitcorp SQE
DefaultDirName={localappdata}\SQE_DailyWork
DefaultGroupName=SQE DailyWork
OutputDir={#OutputDir}
OutputBaseFilename=SQE_DailyWork-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\SQE_DailyWork.exe
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SQE DailyWork"; Filename: "{app}\SQE_DailyWork.exe"
Name: "{userdesktop}\SQE DailyWork"; Filename: "{app}\SQE_DailyWork.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他選項:"

[UninstallDelete]
; Preserve user data on uninstall — do not delete data/ or Outputs/

[Run]
Filename: "{app}\SQE_DailyWork.exe"; Description: "啟動 SQE DailyWork"; Flags: nowait postinstall skipifsilent
