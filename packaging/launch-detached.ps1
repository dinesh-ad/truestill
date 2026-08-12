<#
Launch a process with DETACHED_PROCESS, which is what a double-clicked shortcut gets.

WHY THIS EXISTS. The first Windows measurement (BACKLOG (aad), run 30692798020) used
`Start-Process` from the runner's PowerShell, which owns a console. A GUI-subsystem process
does not get a console ALLOCATED but it still INHERITS one from a parent that has it - the
subsystem field controls allocation, not inheritance - so the probe measured PowerShell's
console and scored Briefcase as "has a console despite console_app = false". It does not.

None of the obvious alternatives are detached:
  * `Start-Process -WindowStyle Hidden` hides a window; the console is still inherited.
  * `ProcessStartInfo` (.NET) exposes no way to set DETACHED_PROCESS at all.
  * CREATE_NO_WINDOW makes an INVISIBLE console, not no console - that distinction is also
    why the AttachConsole test was measuring the wrong thing.

So this calls CreateProcess directly with DETACHED_PROCESS (0x00000008) and returns the child
PID. Throwaway, like everything else in packaging/: delete it with the rig.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string[]]$Arguments = @(),
    [Parameter(Mandatory = $true)][string]$WorkingDirectory
)

$ErrorActionPreference = 'Stop'

Add-Type -Namespace TruestillProbe -Name Native -MemberDefinition @'
[StructLayout(LayoutKind.Sequential)]
public struct PROCESS_INFORMATION {
    public IntPtr hProcess; public IntPtr hThread;
    public uint dwProcessId; public uint dwThreadId;
}

[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
public struct STARTUPINFO {
    public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
    public int dwX; public int dwY; public int dwXSize; public int dwYSize;
    public int dwXCountChars; public int dwYCountChars; public int dwFillAttribute;
    public int dwFlags; public short wShowWindow; public short cbReserved2;
    public IntPtr lpReserved2; public IntPtr hStdInput; public IntPtr hStdOutput;
    public IntPtr hStdError;
}

[DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
public static extern bool CreateProcess(
    string lpApplicationName, string lpCommandLine,
    IntPtr lpProcessAttributes, IntPtr lpThreadAttributes,
    bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment,
    string lpCurrentDirectory, ref STARTUPINFO si, out PROCESS_INFORMATION pi);

[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool CloseHandle(IntPtr hObject);
'@

# Quote every argument: the probe's output path contains the runner's workspace directory.
$quoted = @("`"$Exe`"") + ($Arguments | ForEach-Object { "`"$_`"" })
$commandLine = $quoted -join ' '

$si = New-Object TruestillProbe.Native+STARTUPINFO
$si.cb = [System.Runtime.InteropServices.Marshal]::SizeOf($si)
$pi = New-Object TruestillProbe.Native+PROCESS_INFORMATION

$DETACHED_PROCESS = 0x00000008

$created = [TruestillProbe.Native]::CreateProcess(
    $null, $commandLine, [IntPtr]::Zero, [IntPtr]::Zero,
    $false, $DETACHED_PROCESS, [IntPtr]::Zero, $WorkingDirectory, [ref]$si, [ref]$pi)

if (-not $created) {
    # THE ERROR CODE ALONE HAS COST THREE DISPATCHES. Every run since this script was written
    # (2026-08-01 `30694297381`, and twice on 2026-08-12) has failed here with the same
    # `win32 error 3` - ERROR_PATH_NOT_FOUND - while the build step reported success, and a bare
    # code cannot say WHICH path was not found. CreateProcess is handed three: the executable
    # named inside the command line, the working directory, and whatever the command line parses
    # to when `lpApplicationName` is NULL. So report the state of each at the moment it failed,
    # rather than sending the next person to guess from Linux.
    $code = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    $facts = @(
        "exe exists: $(Test-Path -LiteralPath $Exe)"
        "exe path: '$Exe'"
        "working directory exists: $(Test-Path -LiteralPath $WorkingDirectory -PathType Container)"
        "working directory: '$WorkingDirectory'"
        "command line: $commandLine"
    ) -join '; '
    throw "CreateProcess failed for '$Exe' (win32 error $code) - $facts"
}

[void][TruestillProbe.Native]::CloseHandle($pi.hThread)
[void][TruestillProbe.Native]::CloseHandle($pi.hProcess)

# The PID is the return value; the caller polls it rather than holding a handle.
$pi.dwProcessId
