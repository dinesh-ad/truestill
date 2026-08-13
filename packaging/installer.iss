; The Truestill Windows installer. A RELEASE configuration - unlike the file of the same name
; that lived here until 1c77dd3, which was a throwaway measurement rig.
;
; It comes back as an artifact rather than being rewritten because its SHAPE was already right:
; per-user install, no elevation, the Start-menu / uninstaller / Add-Remove trio, and it was
; already unattended-capable. That is what deleting it *with its findings recorded* bought.
; What did NOT come back is its AppId - see below.
;
; ---------------------------------------------------------------------------------------------
; FOUR REFUSALS, each with a reason rather than a preference, because each will be re-proposed
; by somebody who thinks it is an oversight:
;
;   1. PER-USER, NOT ALL-USERS. An unsigned installer already meets SmartScreen; adding a UAC
;      prompt makes TWO alarming dialogs for a product sold on trust. It also sidesteps the class
;      of the 2026 Briefcase advisory recorded in BACKLOG (aad) - All-Users installers inheriting
;      parent-directory permissions.
;   2. NO ELEVATION. Follows from 1: `PrivilegesRequired=lowest` means the installer never asks.
;   3. NOT ON PATH. Truestill is a double-clicked desktop app, and the person it is for does not
;      have a terminal. Editing a user's PATH is a global side effect to buy them nothing.
;   4. NO FILE ASSOCIATIONS. Truestill organises a library; it is not a photo viewer and must not
;      make itself the thing that opens someone's JPEGs.
; ---------------------------------------------------------------------------------------------
;
; Built by .github/workflows/release.yml, which passes MyAppVersion from the tag.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

[Setup]
; A NEW GUID, generated 2026-08-13, and NEVER the probe's. An AppId is the product's identity for
; upgrade and uninstall: inheriting a deleted measurement rig's GUID would tie the shipped
; product's identity to a throwaway. Once released this must never change again.
AppId={{EA0D2B79-5563-4623-812A-60516EF62F80}
AppName=Truestill
AppVersion={#MyAppVersion}
AppPublisher=truestill
AppPublisherURL=https://github.com/dinesh-ad/truestill
DefaultDirName={autopf}\Truestill
DefaultGroupName=Truestill
UninstallDisplayName=Truestill
; THE FIRST THING A BUYER DOUBLE-CLICKS - before the app, before SmartScreen. Compiled from the
; repository root, which is where release.yml copies this file, so the path is `brand\...`.
; Inno's reference: "If this directive is not specified or is blank, a built-in icon ... will be
; used", and it recommends 16/32/48/64/256 - brand\favicon.ico carries all five (plus 24 and 128).
; THIS ALSO GOVERNS THE UNINSTALLER'S OWN ICON, and there is no second directive to set:
; `UninstallIconFile` is "Obsolete in 5.0.0. As Setup and Uninstall have been merged into a single
; executable, setting a custom icon for Uninstall is no longer possible."
SetupIconFile=brand\favicon.ico
; Points at the installed program, which carries the mark through PyInstaller's `--icon`. Inno
; accepts "either an executable or an .ico file" here, so the exe is the right target: it stays
; correct if the artwork is ever revised, because it names the thing rather than a copy of it.
UninstallDisplayIcon={app}\truestill.exe
OutputDir=inno-out
OutputBaseFilename=TruestillSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; Refusals 1 and 2. With `lowest`, {autopf} resolves to %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
; Nothing here needs a reboot, and offering one implies otherwise.
RestartIfNeededByRun=no
; 64-bit only: the PyInstaller build is.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; The whole one-folder PyInstaller output, which already carries exiftool, both typefaces and the
; Bitstream Vera notice - all three verified by `--self-check` before this installer is built.
Source: "dist\truestill\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Truestill"; Filename: "{app}\truestill.exe"
; The self-check, reachable without a terminal. On a windowed build it writes its report to the
; data directory and opens it - see `_run_self_check`. Without this entry the only way to ask a
; broken install what is broken would be a command line the user does not have.
Name: "{group}\Truestill self-check"; Filename: "{app}\truestill.exe"; Parameters: "--self-check"
Name: "{group}\Uninstall Truestill"; Filename: "{uninstallexe}"

[Code]
{ THE HIGHEST-CONSEQUENCE COPY IN THE ARTIFACT. It is read once, by somebody leaving, and it
  decides whether they believe their library index is gone. An uninstaller that removes a user's
  catalog is the worst possible last impression, so this says - BEFORE anything is removed - what
  goes and what stays, and names the real path rather than describing it.

  There is deliberately no [UninstallDelete] over user data. (aae) draws the line: the catalog is
  unrecoverable user data, the cache is disposable. The uninstaller removes neither.

  SuppressibleMsgBox, NOT MsgBox, and the difference is a 30-minute hang. `/SUPPRESSMSGBOXES` was
  never going to reach a plain `MsgBox`: Inno's own reference says SuppressibleMsgBox "returns the
  Default value without displaying anything to the user, whereas a standard MsgBox would still
  appear". Under `/VERYSILENT /SUPPRESSMSGBOXES` the first version drew a modal dialog nobody could
  click, and the uninstaller sat there until the runner killed `_unins.tmp`. The flag was not
  ignored - it applies to a different function.

  The semantics are exactly what this message wants: a person uninstalling by hand READS IT, at
  the moment before their catalog's fate is decided, and an unattended uninstall proceeds without
  it because there is nobody to read it. IDOK is the default so a scripted removal is not blocked
  by a message that exists for a human. }
function InitializeUninstall(): Boolean;
begin
  SuppressibleMsgBox(
    'Uninstalling Truestill removes the program only.' + #13#10 + #13#10 +
    'Your library index is KEPT, here:' + #13#10 +
    ExpandConstant('{localappdata}\Truestill\catalog.sqlite') + #13#10 + #13#10 +
    'It records which drives hold which photos, and any dates you have confirmed. Truestill '
    + 'never deletes it, and reinstalling will pick it up again.' + #13#10 + #13#10 +
    'Your photos are untouched - Truestill only ever copies them.' + #13#10 + #13#10 +
    'To remove the index as well, delete that file yourself after uninstalling.',
    mbInformation, MB_OK, IDOK);
  Result := True;
end;
