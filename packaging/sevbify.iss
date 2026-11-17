; Sevbify's Windows installer (Inno Setup; built by the automatic build). Installs just for you, no admin
; password: into your own Programs folder, with a Start menu entry (and a desktop one if you tick it) and an
; uninstaller in Settings > Apps. Uninstalling asks whether to also delete your Sevbify data (playlists, settings);
; the answer is No unless you choose Yes. Songs you downloaded into your music folders are never touched.
#ifndef AppVersion
  #define AppVersion "0"
#endif

[Setup]
AppId={{6B1F1C1E-5E0B-4E55-9C59-5EB51F1A2B49}
AppName=Sevbify
AppVersion={#AppVersion}
AppPublisher=Sevbify
DefaultDirName={localappdata}\Programs\Sevbify
DefaultGroupName=Sevbify
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..
OutputBaseFilename=Sevbify-Windows-Setup
SetupIconFile=..\assets\branding\sevbify.ico
UninstallDisplayIcon={app}\Sevbify.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Put Sevbify on the desktop"; Flags: unchecked

[Files]
Source: "..\dist\Sevbify\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Sevbify"; Filename: "{app}\Sevbify.exe"
Name: "{userdesktop}\Sevbify"; Filename: "{app}\Sevbify.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Sevbify.exe"; Description: "Open Sevbify now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Files the app made next to itself (an update's leftovers, the previous version kept for going back).
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{app}.sevbify-previous"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox('Also delete your Sevbify data (playlists, settings, podcasts you follow)?' #13#10#13#10 +
              'Choose No to keep it, so it''s all still there if you install Sevbify again. ' +
              'Songs you downloaded stay in your music folders either way.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\Sevbify'), True, True, True);
end;
