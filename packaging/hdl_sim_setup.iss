; HDL-Sim Windows installer (Inno Setup 6)
; Build: packaging\build_installer.bat

#define AppName "HDL-Sim"
#define AppVersion "0.4.4"
#define AppPublisher "HDL-Sim"
#define AppExeName "HDL-Sim.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=HDL-Sim-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DataDirPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  DataDirPage := CreateInputDirPage(
    wpSelectDir,
    '保存フォルダの選択',
    'プロジェクト (.spj) と projects/ の保存先を選んでください。',
    '後から変更する場合は、インストール先の data_dir.txt を編集してください。',
    False, '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := ExpandConstant('{userdocs}\HDL-Sim');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  DataPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    DataPath := DataDirPage.Values[0];
    SaveStringToFile(ExpandConstant('{app}\data_dir.txt'), DataPath + #13#10, False);
    ForceDirectories(DataPath + '\spj');
    ForceDirectories(DataPath + '\projects');
  end;
end;

[UninstallDelete]
Type: files; Name: "{app}\data_dir.txt"
