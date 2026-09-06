#define MyAppName "Marketplace AI Studio PRO"
#define MyAppVersion "2.3.0"
#define MyAppExeName "Marketplace_AI_Studio_PRO.exe"

[Setup]
AppId={{A08F4F4B-5360-4C8B-A888-6C6F7B1603C3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Marketplace AI Studio PRO
DefaultGroupName=Marketplace AI Studio PRO
OutputDir=installer-output
OutputBaseFilename=Marketplace_AI_Studio_PRO_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible

[Files]
Source: "dist\Marketplace_AI_Studio_PRO.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Marketplace AI Studio PRO"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\Marketplace AI Studio PRO"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить Marketplace AI Studio PRO"; Flags: nowait postinstall skipifsilent
