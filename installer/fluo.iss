; Instalador de Fluo (Inno Setup 6)
; Compilar desde la raíz del repo, después de PyInstaller:
;   iscc /DMyAppVersion=0.1.0 installer\fluo.iss
; Instala por usuario (sin administrador) en %LOCALAPPDATA%\Programs\Fluo.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Fluo"
#define MyAppPublisher "Nicolás Miné"
#define MyAppURL "https://github.com/nicomine-dev/fluo"
#define MyAppExeName "Fluo.exe"

[Setup]
AppId={{7E1C9C4B-5B3D-4C1E-9A0F-2D6B8E4F1A37}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Fluo-Setup-{#MyAppVersion}
SetupIconFile=..\fluo\resources\fluo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "openwith"; Description: "Agregar «Abrir con Fluo» al menú contextual de los PDF"; GroupDescription: "Integración:"

[Files]
Source: "..\dist\Fluo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; "Abrir con" para PDFs, solo para este usuario (HKCU), sin robar la asociación por defecto.
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKCU; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: openwith
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithList\{#MyAppExeName}"; ValueType: none; Flags: uninsdeletekey; Tasks: openwith

[Run]
; Sin "skipifsilent": cuando el actualizador corre el instalador en silencio, la app vuelve a abrirse sola.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
