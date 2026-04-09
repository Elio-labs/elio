[Setup]
AppName=Elio
AppVersion=0.2.6
DefaultDirName={localappdata}\ElioCLI
OutputDir=dist
OutputBaseFilename=Elio-Setup
Compression=lzma
SolidCompression=yes
ChangesEnvironment=yes
DisableProgramGroupPage=yes
AppPublisher=Elio Labs
UninstallDisplayName=Elio CLI v0.2.6

[Files]
Source: "dist\elio.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app}\bin;{olddata}"; Check: NeedsAddPath(ExpandConstant('{app}\bin'))

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + UpperCase(Param) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C setx PATH ""%TEMP%"" && setx PATH ""{olddata}"""; Flags: runhidden

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OrigPath, AppBin, NewPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppBin := ExpandConstant('{app}\bin');
    if RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
    begin
      NewPath := StringReplace(OrigPath, ';' + AppBin, '', [rfReplaceAll, rfIgnoreCase]);
      NewPath := StringReplace(NewPath, AppBin + ';', '', [rfReplaceAll, rfIgnoreCase]);
      NewPath := StringReplace(NewPath, AppBin, '', [rfReplaceAll, rfIgnoreCase]);
      RegWriteExpandStrValue(HKCU, 'Environment', 'Path', NewPath);
    end;
  end;
end;