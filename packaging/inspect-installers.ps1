# What each installer PUTS ON THE MACHINE, for the (aad) installer comparison.
#
# Throwaway measurement, not a release script - see the scope fence in
# .github/workflows/packaging-throwaway.yml.
#
# THE POINT: "install experience" stated as something measurable. Install location, Start-menu
# entry, uninstaller registration, and whether it appears in Add/Remove Programs - which IS the
# three uninstall registry keys read below, so it is a fact rather than a preference.
#
# Everything installs SILENTLY and uninstalls again: a runner cannot click a wizard, and leaving
# an install behind would make the second measurement read the first one's registrations.
#
# A packaging step that FAILED still produces a findings file saying so. "No file" must never be
# ambiguous between a failed build and a job that never ran - the lesson the first run of this
# rig already paid for.

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path findings | Out-Null

# Add/Remove Programs is exactly these keys. Reading them IS the measurement; there is no
# separate "does it appear in the list" to check.
$uninstallRoots = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
)
$startMenus = @(
    (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
)

function Get-Registration {
    $rows = @()
    foreach ($root in $uninstallRoots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($key in Get-ChildItem $root -ErrorAction SilentlyContinue) {
            $props = Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue
            if ($props.DisplayName -like '*Truestill*') {
                $rows += [ordered]@{
                    hive              = $root
                    key               = $key.PSChildName
                    display_name      = $props.DisplayName
                    display_version   = $props.DisplayVersion
                    publisher         = $props.Publisher
                    install_location  = $props.InstallLocation
                    uninstall_string  = $props.UninstallString
                    estimated_size_kb = $props.EstimatedSize
                }
            }
        }
    }
    return @($rows)
}

function Get-Shortcuts {
    $found = @()
    foreach ($menu in $startMenus) {
        if (-not (Test-Path $menu)) { continue }
        $found += @(Get-ChildItem $menu -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like '*Truestill*' } |
            ForEach-Object { $_.FullName })
    }
    return @($found)
}

function Write-Findings {
    param([string]$Name, $Body)
    $json = $Body | ConvertTo-Json -Depth 6
    Set-Content -Path "findings\$Name.json" -Value $json -Encoding utf8
    Write-Host "--- $Name ---"
    Write-Host $json
}

# ---------------------------------------------------------------- Inno Setup ----------------
if ($env:INNO_OUTCOME -ne 'success') {
    Write-Findings 'installer-inno' ([ordered]@{
        bundler = 'pyinstaller+inno'
        built   = $false
        note    = "packaging step outcome was '$($env:INNO_OUTCOME)' - nothing to install"
    })
}
else {
    $setup = Get-ChildItem -Path inno-out -Filter '*.exe' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $before = (Get-Registration).Count
    & $setup.FullName /VERYSILENT /SUPPRESSMSGBOXES /NORESTART | Out-Null
    Start-Sleep -Seconds 5

    $registrations = Get-Registration
    $body = [ordered]@{
        bundler         = 'pyinstaller+inno'
        built           = $true
        installer_name  = $setup.Name
        installer_bytes = $setup.Length
        registrations   = $registrations
        in_add_remove   = ($registrations.Count -gt $before)
        start_menu_lnks = Get-Shortcuts
    }

    foreach ($row in $registrations) {
        if ($row.uninstall_string) {
            $exe = $row.uninstall_string -replace '^"([^"]+)".*$', '$1'
            if (Test-Path $exe) { & $exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART | Out-Null }
        }
    }
    Start-Sleep -Seconds 5
    $body['uninstalled_cleanly'] = ((Get-Registration).Count -le $before)
    Write-Findings 'installer-inno' $body
}

# ---------------------------------------------------------------- Briefcase MSI -------------
if ($env:BRIEFCASE_OUTCOME -ne 'success') {
    Write-Findings 'installer-briefcase' ([ordered]@{
        bundler = 'briefcase-msi'
        built   = $false
        note    = "packaging step outcome was '$($env:BRIEFCASE_OUTCOME)' - nothing to install"
    })
}
else {
    $msi = Get-ChildItem -Path packaging\dist -Filter '*.msi' -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $before = (Get-Registration).Count
    Start-Process msiexec.exe -Wait -ArgumentList @('/i', "`"$($msi.FullName)`"", '/qn', '/norestart')
    Start-Sleep -Seconds 5

    $registrations = Get-Registration
    $body = [ordered]@{
        bundler         = 'briefcase-msi'
        built           = $true
        installer_name  = $msi.Name
        installer_bytes = $msi.Length
        registrations   = $registrations
        in_add_remove   = ($registrations.Count -gt $before)
        start_menu_lnks = Get-Shortcuts
    }

    foreach ($row in $registrations) {
        # An MSI's uninstall key IS its ProductCode GUID, which is what msiexec /x wants.
        if ($row.key -match '^\{[0-9A-Fa-f-]+\}$') {
            Start-Process msiexec.exe -Wait -ArgumentList @('/x', $row.key, '/qn', '/norestart')
        }
    }
    Start-Sleep -Seconds 5
    $body['uninstalled_cleanly'] = ((Get-Registration).Count -le $before)
    Write-Findings 'installer-briefcase' $body
}
