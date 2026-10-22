; Instalador do MacPronto (Inno Setup 6). Gerado por scripts/build.py:
;   ISCC /DAppVersion=0.1.0 /DSourceDir=..\dist\MacPronto /O..\dist installer\MacPronto.iss

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\MacPronto"
#endif

[Setup]
AppId={{B7F5A2E1-6C3D-4E8A-9F21-4D7C3A5E8B10}
AppName=MacPronto
AppVersion={#AppVersion}
AppVerName=MacPronto {#AppVersion}
AppPublisher=Patrick da Costa Cruz
AppPublisherURL=https://github.com/patrickccruz/MacPronto
AppSupportURL=https://github.com/patrickccruz/MacPronto
DefaultDirName={autopf}\MacPronto
DefaultGroupName=MacPronto
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputBaseFilename=MacPronto-{#AppVersion}-instalador
SetupIconFile=..\assets\macpronto.ico
UninstallDisplayIcon={app}\MacPronto.exe
UninstallDisplayName=MacPronto
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
MinVersion=10.0.17763

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MacPronto"; Filename: "{app}\MacPronto.exe"
Name: "{autoprograms}\Política de Uso do MacPronto"; Filename: "{app}\POLITICA-DE-USO.md"
Name: "{autodesktop}\MacPronto"; Filename: "{app}\MacPronto.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MacPronto.exe"; Description: "{cm:LaunchProgram,MacPronto}"; Flags: nowait postinstall skipifsilent shellexec

[Code]
const
  WebView2Key = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2UserKey = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function WebView2Installed(): Boolean;
var
  Version: String;
begin
  Result := (RegQueryStringValue(HKLM, WebView2Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
            (RegQueryStringValue(HKCU, WebView2UserKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if (CurStep = ssPostInstall) and not WebView2Installed() then
  begin
    if MsgBox('O MacPronto usa o Microsoft Edge WebView2, que não foi encontrado neste computador.' + #13#10 +
              'Deseja abrir a página da Microsoft para instalá-lo?', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;
