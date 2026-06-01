; HDL-Sim Windows installer (Inno Setup 6)
; Build: packaging\build_installer.bat

#define AppName "HDL-Sim"
#define AppVersion "0.5.0"
#define AppPublisher "HDL-Sim"
#define AppExeName "HDL-Sim.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=HDL-Sim-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
Uninstallable=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
CreateUninstallRegKey=yes
UpdateUninstallLogAppName=yes
CloseApplications=force
RestartApplications=no

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "ショートカットの作成:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "クイック起動にショートカットを作成する"; GroupDescription: "ショートカットの作成:"; Flags: checkedonce; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode
Name: "launchapp"; Description: "インストール完了後に {#AppName} を起動する"; GroupDescription: "その他:"; Flags: checkedonce

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "Verilog HDL シミュレータ IDE"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Comment: "Verilog HDL シミュレータ IDE"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon; Comment: "Verilog HDL シミュレータ IDE"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent; Tasks: launchapp

[UninstallRun]
Filename: "taskkill"; Parameters: "/F /IM {#AppExeName}"; Flags: runhidden; RunOnceId: "KillHDL-Sim"

[UninstallDelete]
Type: files; Name: "{app}\data_dir.txt"

[Code]
var
  DataDirPage: TInputDirWizardPage;

function ReadDataDirConfig(AppDir: String): String;
var
  Lines: TArrayOfString;
begin
  Result := '';
  if not LoadStringsFromFile(AppDir + '\data_dir.txt', Lines) then
    Exit;
  if GetArrayLength(Lines) >= 1 then
    Result := Trim(Lines[0]);
end;

procedure DeleteDirRecursive(Dir: String);
var
  FindRec: TFindRec;
  Path: String;
begin
  if not DirExists(Dir) then
    Exit;
  if FindFirst(Dir + '\*', FindRec) then
  try
    repeat
      if (FindRec.Name = '.') or (FindRec.Name = '..') then
        Continue;
      Path := Dir + '\' + FindRec.Name;
      if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
        DeleteDirRecursive(Path)
      else
        DeleteFile(Path);
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
  RemoveDir(Dir);
end;

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

function UninstallConfirm(): Boolean;
begin
  Result := True;
  if MsgBox(
    'HDL-Sim をアンインストールします。' + #13#10 +
    '続行しますか？',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDNO then
    Result := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir, DataPath: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    DataPath := ReadDataDirConfig(AppDir);
    if (DataPath <> '') and DirExists(DataPath) then
    begin
      if MsgBox(
        '保存フォルダ内のユーザーデータも削除しますか？' + #13#10 + #13#10 +
        DataPath + #13#10 + #13#10 +
        '「はい」= プロジェクト / .spj も削除' + #13#10 +
        '「いいえ」= アプリのみ削除（データは残す）',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DeleteDirRecursive(DataPath + '\spj');
        DeleteDirRecursive(DataPath + '\projects');
        if (DirExists(DataPath + '\spj') = False) and
           (DirExists(DataPath + '\projects') = False) then
          RemoveDir(DataPath);
      end;
    end;
  end;
end;
