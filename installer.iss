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
; Add to PATH on install
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{app}\bin;{olddata}"; Check: NeedsAddPath(ExpandConstant('{app}\bin'))

[Code]

{ ── Install helpers ── }

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

{ ── Uninstall: remove app\bin from PATH ── }

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OrigPath, AppBin, NewPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppBin := ExpandConstant('{app}\bin');
    if RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
    begin
      { Strip all three possible forms: leading, trailing, or middle }
      NewPath := StringReplace(OrigPath, AppBin + ';', '', [rfReplaceAll, rfIgnoreCase]);
      NewPath := StringReplace(NewPath,  ';' + AppBin, '', [rfReplaceAll, rfIgnoreCase]);
      NewPath := StringReplace(NewPath,  AppBin,       '', [rfReplaceAll, rfIgnoreCase]);
      RegWriteExpandStrValue(HKCU, 'Environment', 'Path', NewPath);
    end;
  end;
end;
