#define AppName "B.S. Portal"
#define AppVersion "0.2.0-alpha"
#define AppPublisher "B.S. Supply Co."
#define AppExeName "BS-Portal.exe"

// BundleMySql and BundleVcRedist are defined explicitly by build_release.ps1
// only when -BundleDependencies is requested. Cached vendor files alone never
// change the redistribution behavior of a normal online installer build.

[Setup]
AppId={{9C7F77B7-403D-4D68-9AB1-1B8D7D7D9E69}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\B.S. Supply Co\B.S. Portal
DefaultGroupName=B.S. Portal
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\release\windows
OutputBaseFilename=BS-Portal-v{#AppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE
CloseApplications=yes
CloseApplicationsFilter=BS-Portal.exe
RestartApplications=no
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoVersion=0.2.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=B.S. Portal Windows installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Files]
Source: "..\..\dist\windows\BS-Portal.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "install_runtime.ps1"; Flags: dontcopy
#ifdef BundleMySql
Source: "vendor\mysql-8.4.11-winx64.zip"; Flags: dontcopy
#endif
#ifdef BundleVcRedist
Source: "vendor\vc_redist.x64.exe"; Flags: dontcopy
#endif

[Icons]
Name: "{autoprograms}\B.S. Portal"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\B.S. Portal"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch B.S. Portal"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  InstallScript: String;
  Params: String;
begin
  if CurStep = ssPostInstall then
  begin
    ExtractTemporaryFile('install_runtime.ps1');
    InstallScript := ExpandConstant('{tmp}\install_runtime.ps1');

    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + InstallScript + '"' +
      ' -AppDir "' + ExpandConstant('{app}') + '"' +
      ' -DataDir "' + ExpandConstant('{commonappdata}\B.S. Supply Co\B.S. Portal') + '"' +
      ' -AppExe "' + ExpandConstant('{app}\{#AppExeName}') + '"';

#ifdef BundleMySql
    ExtractTemporaryFile('mysql-8.4.11-winx64.zip');
    Params := Params + ' -BundledMySqlZip "' + ExpandConstant('{tmp}\mysql-8.4.11-winx64.zip') + '"';
#endif
#ifdef BundleVcRedist
    ExtractTemporaryFile('vc_redist.x64.exe');
    Params := Params + ' -BundledVcRedist "' + ExpandConstant('{tmp}\vc_redist.x64.exe') + '"';
#endif

    if not Exec(
      ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      Params,
      '',
      SW_SHOW,
      ewWaitUntilTerminated,
      ResultCode
    ) then
      RaiseException('Could not start the B.S. Portal runtime installer.');

    if ResultCode <> 0 then
      RaiseException(Format('B.S. Portal runtime setup failed with exit code %d.', [ResultCode]));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec(ExpandConstant('{sys}\sc.exe'), 'stop BSPortalMySQL', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\sc.exe'), 'delete BSPortalMySQL', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
