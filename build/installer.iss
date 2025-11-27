; PHYS-2150 Measurement Suite - Inno Setup Installer Script
;
; Build instructions:
; 1. First build the application with PyInstaller:
;    uv run pyinstaller build/phys2150.spec
;
; 2. Then build the installer with Inno Setup:
;    iscc build/installer.iss
;
; Output: dist/PHYS2150-Setup.exe
;
; Prerequisites on target machine:
; - Windows 10/11 64-bit
; - NI-VISA Runtime (for instrument communication)
; - PicoScope SDK (for EQE measurements)
; - Thorlabs OPM driver (for power meter)
; - Newport MonoUtility (for monochromator)

#define MyAppName "PHYS-2150 Measurement Suite"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "CU Boulder Physics Lab"
#define MyAppURL "https://github.com/UCBoulder/PHYS-2150"
#define MyAppExeName "PHYS2150.exe"

[Setup]
; Application metadata
AppId={{E8A7B3C4-5D6F-4E2A-B1C9-D0E8F7A6B5C4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation paths
DefaultDirName={autopf}\PHYS-2150
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output configuration
OutputDir=..\dist
OutputBaseFilename=PHYS2150-Setup
SetupIconFile=
; Uncomment and set icon path if available:
; SetupIconFile=..\assets\icon.ico

; Compression settings
Compression=lzma2
SolidCompression=yes

; Windows version requirements
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Installation mode
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Visual settings
WizardStyle=modern
WizardResizable=no

; License and info pages (optional - uncomment if files exist)
; LicenseFile=..\LICENSE
; InfoBeforeFile=..\docs\pre-install-info.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files from PyInstaller output
Source: "..\dist\PHYS2150\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Note: Make sure to run PyInstaller first to generate the dist/PHYS2150 folder

[Icons]
; Start Menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Launch PHYS-2150 Measurement Suite"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Launch PHYS-2150 Measurement Suite"

[Run]
; Launch application after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Pascal script for custom installation checks

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  // Check for NI-VISA installation (optional warning)
  if not FileExists(ExpandConstant('{sys}\visa32.dll')) then
  begin
    if MsgBox('NI-VISA Runtime was not detected.' + #13#10 + #13#10 +
              'NI-VISA is required for instrument communication.' + #13#10 +
              'The application may not function correctly without it.' + #13#10 + #13#10 +
              'Do you want to continue with the installation anyway?',
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks can be added here
    // For example, creating a data directory or copying default config
  end;
end;

[UninstallDelete]
; Clean up application data on uninstall (optional)
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\cache"

[Messages]
; Custom messages
WelcomeLabel2=This will install [name/ver] on your computer.%n%nIMPORTANT: This application requires the following hardware drivers to be pre-installed:%n%n- NI-VISA Runtime%n- PicoScope SDK%n- Thorlabs OPM driver%n- Newport MonoUtility%n%nPlease ensure these are installed before using the application.