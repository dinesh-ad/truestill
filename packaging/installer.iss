; Inno Setup script for the (aad) INSTALLER COMPARISON. Throwaway measurement, not a release
; configuration - see .github/workflows/packaging-throwaway.yml for the scope fence.
;
; Deliberately minimal but REPRESENTATIVE. The three things a non-technical user actually meets
; are a Start-menu entry, an uninstaller, and a row in Add/Remove Programs. A script omitting
; them would measure Inno Setup at its worst and flatter the MSI by comparison, which would
; answer a question nobody asked.
;
; PrivilegesRequired=lowest: installs per-user, so the measurement needs no elevation on a
; runner and reflects what a user without an administrator account would get.

[Setup]
AppId={{9F1A2B3C-4D5E-6F70-8192-A3B4C5D6E7F8}
AppName=Truestill Probe
AppVersion=0.0.1
AppPublisher=truestill
DefaultDirName={autopf}\TruestillProbe
DefaultGroupName=Truestill Probe
UninstallDisplayName=Truestill Probe
OutputDir=inno-out
OutputBaseFilename=TruestillProbe-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "dist\TruestillProbe\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Truestill Probe"; Filename: "{app}\TruestillProbe.exe"
