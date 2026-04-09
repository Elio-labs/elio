[Setup]
AppName=Elio
AppVersion=0.1.0
AppPublisher=Elio Labs
UninstallDisplayName=Elio CLI v0.1.0
DefaultDirName={localappdata}\ElioCLI
OutputDir=dist
OutputBaseFilename=Elio-Setup
Compression=lzma
SolidCompression=yes
ChangesEnvironment=yes
DisableProgramGroupPage=yes

[Files]
Source: "dist\elio.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app}\bin;{olddata}"; Check: NeedsAddPath(ExpandConstant('{app}\bin'))

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + UpperCase(Param) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OrigPath, AppBin: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppBin := ExpandConstant('{app}\bin');
    if RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
    begin
      StringChange(OrigPath, AppBin + ';', '');
      StringChange(OrigPath, ';' + AppBin, '');
      StringChange(OrigPath, AppBin, '');
      RegWriteExpandStrValue(HKCU, 'Environment', 'Path', OrigPath);
    end;
  end;
end;