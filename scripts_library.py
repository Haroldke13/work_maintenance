"""PowerShell helpers officers run on a machine before filling in the report.

Every entry produces a report the officer can paste straight into one field of
the NGOB/ICT/104b form. Each script is offered two ways:

* ``.ps1`` — re-launches itself elevated, then runs.
* ``.cmd`` — elevates, unpacks the same PowerShell to ``%TEMP%``, and runs it.

The PowerShell body is the single source of truth; the ``.cmd`` wrapper is
generated from it, so a script is only ever written once.
"""

import base64
import textwrap

from form_schema import field_label

__all__ = [
    "MAINTENANCE_SCRIPTS",
    "script_groups",
    "find_script",
    "powershell_file",
    "cmd_file",
]


def _report(title: str, body: str) -> str:
    """Wrap a collector in the common preamble, clipboard copy, and desktop save."""
    return textwrap.dedent(
        f"""\
        # {title}
        # Public Benefit Organizations Regulatory Authority - ICT
        # Computer Maintenance Report (NGOB/ICT/104b)
        #
        # Run this on the computer being serviced, then paste the report into the
        # matching field of the maintenance form. The result is also copied to the
        # clipboard and saved to the Desktop.

        # --- Run elevated -------------------------------------------------------
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
            Start-Process powershell.exe -Verb RunAs -ArgumentList @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
            )
            exit
        }}

        $ErrorActionPreference = 'Continue'
        $title = '{title}'

        # --- Collect ------------------------------------------------------------
        $report = @(
            "=== $title ==="
            "Computer: $env:COMPUTERNAME    Collected: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
            ""
{textwrap.indent(body.rstrip(), " " * 12)}
        )

        # --- Report -------------------------------------------------------------
        $file = Join-Path ([Environment]::GetFolderPath('Desktop')) '{title.replace(" ", "-")}.txt'
        $report | Tee-Object -FilePath $file
        try {{ $report -join "`r`n" | Set-Clipboard; Write-Host "`nCopied to the clipboard." }} catch {{ }}
        Write-Host "Saved to $file"
        notepad.exe $file
        """
    )


MAINTENANCE_SCRIPTS = [
    # -- Report details ----------------------------------------------------
    {
        "key": "chassis-serial-number",
        "title": "Chassis SNo from BIOS",
        "group": "Report Details",
        "field": "serial_no",
        "summary": "Chassis serial number as the BIOS reports it.",
        "body": """\
$bios = Get-CimInstance Win32_BIOS
$enclosure = Get-CimInstance Win32_SystemEnclosure
$product = Get-CimInstance Win32_ComputerSystemProduct

"BIOS serial number  : $($bios.SerialNumber)"
"Enclosure serial    : $($enclosure.SerialNumber)"
"Asset tag           : $($enclosure.SMBIOSAssetTag)"
"UUID                : $($product.UUID)"
"BIOS version        : $($bios.SMBIOSBIOSVersion) ($($bios.Manufacturer))"
"Computer name       : $env:COMPUTERNAME"

""
"Record the BIOS serial number above as the chassis SNo."
""",
    },
    {
        "key": "chassis-model",
        "title": "Chassis Model from BIOS",
        "group": "Report Details",
        "field": "computer_name",
        "summary": "Make and model held in the BIOS, e.g. HP ProBook G5.",
        "body": """\
$system = Get-CimInstance Win32_ComputerSystem
$product = Get-CimInstance Win32_ComputerSystemProduct
$enclosure = Get-CimInstance Win32_SystemEnclosure

$chassisNames = @{
    3 = 'Desktop'; 4 = 'Low profile desktop'; 6 = 'Mini tower'; 7 = 'Tower'
    8 = 'Portable'; 9 = 'Laptop'; 10 = 'Notebook'; 13 = 'All in one'
    23 = 'Rack mount'; 30 = 'Tablet'; 31 = 'Convertible'; 32 = 'Detachable'
}
$chassisType = [int]($enclosure.ChassisTypes | Select-Object -First 1)
$chassisLabel = $chassisNames[$chassisType]
if (-not $chassisLabel) { $chassisLabel = "Type $chassisType" }

"Manufacturer    : $($system.Manufacturer)"
"Model           : $($system.Model)"
"Product name    : $($product.Name)"
"Product version : $($product.Version)"
"System family   : $($system.SystemFamily)"
"Chassis type    : $chassisLabel"

""
"Record the manufacturer and model above, e.g. HP ProBook 640 G5."
""",
    },
    {
        "key": "desktop-serial-number",
        "title": "Desktop SNo",
        "group": "Report Details",
        "field": "desktop_sno",
        "summary": "Serial number of the desktop unit, to check against its sticker.",
        "body": """\
$product = Get-CimInstance Win32_ComputerSystemProduct
$enclosure = Get-CimInstance Win32_SystemEnclosure
$baseboard = Get-CimInstance Win32_BaseBoard

"Identifying number : $($product.IdentifyingNumber)"
"Enclosure serial   : $($enclosure.SerialNumber)"
"Baseboard serial   : $($baseboard.SerialNumber)"
"Asset tag          : $($enclosure.SMBIOSAssetTag)"
"Computer name      : $env:COMPUTERNAME"

""
"Check these against the serial number printed on the desktop unit itself,"
"and record the number on the sticker."
""",
    },
    {
        "key": "desktop-model",
        "title": "Desktop Model",
        "group": "Report Details",
        "field": "desktop_model",
        "summary": "Make, model, memory, and OS of the desktop, e.g. HP ProDesk 400 G7.",
        "body": """\
$system = Get-CimInstance Win32_ComputerSystem
$product = Get-CimInstance Win32_ComputerSystemProduct

"Manufacturer : $($system.Manufacturer)"
"Model        : $($system.Model)"
"Product name : $($product.Name)"
"System type  : $($system.SystemType)"
"Memory       : $([math]::Round($system.TotalPhysicalMemory / 1GB, 1)) GB"
"OS           : $((Get-CimInstance Win32_OperatingSystem).Caption)"

""
"Record the manufacturer and model above, e.g. HP ProDesk 400 G7."
""",
    },
    # -- Services ----------------------------------------------------------
    {
        "key": "data-backup-schedule",
        "title": "Status of data backup schedule",
        "group": "Services",
        "field": "data_backup_schedule_status",
        "summary": "Windows Backup / File History state and scheduled backup tasks.",
        "body": """\
"--- Windows Backup (wbadmin) ---"
$wb = wbadmin get status 2>&1
if ($LASTEXITCODE -ne 0 -or -not $wb) { "Windows Server Backup not installed." } else { $wb }

""
"--- File History ---"
$fh = Get-Service -Name fhsvc -ErrorAction SilentlyContinue
if ($fh) { "File History service: $($fh.Status) (startup $((Get-CimInstance Win32_Service -Filter "Name='fhsvc'").StartMode))" }
else { "File History service not present." }

""
"--- Scheduled backup tasks ---"
$tasks = Get-ScheduledTask | Where-Object { $_.TaskName -match 'backup|Backup' }
if ($tasks) {
    $tasks | ForEach-Object {
        $info = $_ | Get-ScheduledTaskInfo
        "$($_.TaskName) [$($_.State)] last run $($info.LastRunTime) result $($info.LastTaskResult)"
    }
} else { "No scheduled tasks matching 'backup'." }""",
    },
    {
        "key": "google-drive-update",
        "title": "Google Drive update check",
        "group": "Services",
        "field": "data_backup_schedule_status",
        "summary": "Installed Google Drive version, sync process, and update task.",
        "body": """\
"--- Installed version ---"
$paths = @(
    'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
$installed = Get-ItemProperty $paths -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -match 'Google Drive' }
if ($installed) {
    $installed | ForEach-Object { "$($_.DisplayName) version $($_.DisplayVersion)" }
} else { "Google Drive is not installed." }

""
"--- Executable on disk ---"
$exe = 'C:\\Program Files\\Google\\Drive File Stream\\GoogleDriveFS.exe'
if (Test-Path $exe) {
    $item = Get-Item $exe
    "File version : $($item.VersionInfo.FileVersion)"
    "Last written : $($item.LastWriteTime)"
} else { "GoogleDriveFS.exe not found in the default location." }

""
"--- Running / update task ---"
$proc = Get-Process -Name GoogleDriveFS -ErrorAction SilentlyContinue
if ($proc) { "Google Drive is running (PID $($proc.Id -join ', '))." } else { "Google Drive is not running." }
$task = Get-ScheduledTask | Where-Object { $_.TaskName -match 'Google' }
if ($task) {
    $task | ForEach-Object { "Task $($_.TaskName) [$($_.State)] last run $(($_ | Get-ScheduledTaskInfo).LastRunTime)" }
} else { "No Google scheduled update task registered." }""",
    },
    {
        "key": "windows-firewall-status",
        "title": "Windows firewall status",
        "group": "Services",
        "field": "windows_firewall_status",
        "summary": "Enabled state and default actions of all three firewall profiles.",
        "body": """\
Get-NetFirewallProfile | ForEach-Object {
    "$($_.Name) profile: enabled=$($_.Enabled) inbound=$($_.DefaultInboundAction) outbound=$($_.DefaultOutboundAction)"
}
""
"Firewall service: $((Get-Service MpsSvc).Status)\"""",
    },
    {
        "key": "firewall-exceptions",
        "title": "Allowed firewall exceptions",
        "group": "Services",
        "field": "allowed_firewall_exceptions",
        "summary": "Enabled inbound Allow rules, one per line.",
        "body": """\
$rules = Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow |
    Sort-Object DisplayName
"Enabled inbound allow rules: $($rules.Count)"
""
$rules | ForEach-Object { $_.DisplayName }""",
    },
    {
        "key": "windows-update-status",
        "title": "Windows update status",
        "group": "Services",
        "field": "windows_update_status",
        "summary": "Last installed updates and any pending ones.",
        "body": """\
"--- Service ---"
"Windows Update service: $((Get-Service wuauserv).Status)"

""
"--- Recently installed ---"
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 |
    ForEach-Object { "$($_.HotFixID) $($_.Description) installed $($_.InstalledOn)" }

""
"--- Pending updates ---"
try {
    $searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
    $pending = $searcher.Search("IsInstalled=0 and Type='Software'").Updates
    if ($pending.Count -eq 0) { "No pending updates." }
    else { $pending | ForEach-Object { $_.Title } }
} catch { "Could not query pending updates: $($_.Exception.Message)" }""",
    },
    {
        "key": "unneeded-running-services",
        "title": "Unneeded running system services",
        "group": "Services",
        "field": "unneeded_running_services",
        "summary": "Running services from the usual switch-off list, plus all automatic ones.",
        "body": """\
$watch = 'Fax', 'WMPNetworkSvc', 'RemoteRegistry', 'XblGameSave', 'XboxNetApiSvc',
         'MapsBroker', 'RetailDemo', 'PrintNotify', 'Spooler', 'TabletInputService',
         'WerSvc', 'DiagTrack', 'dmwappushservice'

"--- Commonly unneeded services that are running ---"
$hits = Get-Service -Name $watch -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Running' }
if ($hits) { $hits | ForEach-Object { "$($_.Name) - $($_.DisplayName)" } }
else { "None of the usual candidates are running." }

""
"--- All running services set to start automatically ---"
Get-CimInstance Win32_Service -Filter "State='Running' AND StartMode='Auto'" |
    Sort-Object DisplayName | ForEach-Object { "$($_.Name) - $($_.DisplayName)" }""",
    },
    {
        "key": "autoruns",
        "title": "List of autoruns",
        "group": "Services",
        "field": "autoruns",
        "summary": "Startup entries from the registry, the Startup folders, and scheduled logon tasks.",
        "body": """\
"--- Registry Run keys ---"
$keys = @(
    'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run',
    'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce',
    'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Run',
    'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run',
    'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce'
)
foreach ($key in $keys) {
    if (-not (Test-Path $key)) { continue }
    $entry = Get-ItemProperty $key
    $entry.PSObject.Properties |
        Where-Object { $_.Name -notlike 'PS*' } |
        ForEach-Object { "$($_.Name) -> $($_.Value)" }
}

""
"--- Startup folders ---"
$folders = @(
    [Environment]::GetFolderPath('Startup'),
    [Environment]::GetFolderPath('CommonStartup')
)
foreach ($folder in $folders) {
    Get-ChildItem $folder -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Name) ($folder)" }
}

""
"--- Startup apps reported by WMI ---"
Get-CimInstance Win32_StartupCommand | ForEach-Object { "$($_.Name) [$($_.Location)] -> $($_.Command)" }

""
"--- Scheduled tasks that run at logon or startup ---"
Get-ScheduledTask | Where-Object {
    $_.State -ne 'Disabled' -and $_.Triggers.CimClass.CimClassName -match 'Logon|Boot'
} | ForEach-Object { "$($_.TaskPath)$($_.TaskName) [$($_.State)]" }""",
    },
    {
        "key": "unneeded-software",
        "title": "Unneeded software installations",
        "group": "Services",
        "field": "unneeded_software",
        "summary": "Every installed program with its version and install date.",
        "body": """\
$paths = @(
    'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',
    'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
)
Get-ItemProperty $paths -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName } |
    Sort-Object DisplayName -Unique |
    ForEach-Object { "$($_.DisplayName) | $($_.DisplayVersion) | installed $($_.InstallDate)" }""",
    },
    {
        "key": "antivirus-status",
        "title": "Anti-virus auto-protect status",
        "group": "Services",
        "field": "antivirus_auto_protect_status",
        "summary": "Registered anti-virus products and Defender real-time protection.",
        "body": """\
"--- Registered anti-virus products ---"
try {
    Get-CimInstance -Namespace root\\SecurityCenter2 -ClassName AntiVirusProduct |
        ForEach-Object { "$($_.displayName) (state code $('0x{0:X}' -f $_.productState))" }
} catch { "Could not read the Security Center: $($_.Exception.Message)" }

""
"--- Microsoft Defender ---"
try {
    $status = Get-MpComputerStatus
    "Real-time protection : $($status.RealTimeProtectionEnabled)"
    "Antivirus enabled    : $($status.AntivirusEnabled)"
    "Signature version    : $($status.AntivirusSignatureVersion)"
    "Signatures updated   : $($status.AntivirusSignatureLastUpdated)"
    "Last quick scan      : $($status.QuickScanEndTime)"
} catch { "Microsoft Defender is not available on this machine." }""",
    },
    {
        "key": "windows-user-accounts",
        "title": "Windows user accounts",
        "group": "Services",
        "field": "windows_user_accounts",
        "summary": "Local accounts, their state, and administrator group membership.",
        "body": """\
"--- Local accounts ---"
Get-LocalUser | Sort-Object Name | ForEach-Object {
    "$($_.Name) | enabled=$($_.Enabled) | last logon $($_.LastLogon) | password last set $($_.PasswordLastSet)"
}

""
"--- Members of Administrators ---"
Get-LocalGroupMember -Group 'Administrators' -ErrorAction SilentlyContinue |
    ForEach-Object { "$($_.Name) [$($_.ObjectClass)]" }""",
    },
    {
        "key": "free-disk-space",
        "title": "Free disk space",
        "group": "Services",
        "field": "free_disk_space",
        "summary": "Free and total space on every fixed drive.",
        "body": """\
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    $free = [math]::Round($_.FreeSpace / 1GB, 1)
    $size = [math]::Round($_.Size / 1GB, 1)
    $percent = if ($_.Size) { [math]::Round($_.FreeSpace / $_.Size * 100, 1) } else { 0 }
    "$($_.DeviceID) $free GB free of $size GB ($percent% free)"
}""",
    },
    {
        "key": "disk-defragmentation",
        "title": "Disk defragmentation",
        "group": "Services",
        "field": "disk_defragmentation_done",
        "summary": "Analyses each volume and reports fragmentation, then shows the optimise history.",
        "body": """\
"--- Volume analysis ---"
Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' } | ForEach-Object {
    $letter = $_.DriveLetter
    $media = (Get-PhysicalDisk | Where-Object { $_.DeviceId -eq 0 }).MediaType
    $analysis = Optimize-Volume -DriveLetter $letter -Analyze -Verbose 4>&1
    "Drive ${letter}: media=$media"
    $analysis | ForEach-Object { "  $_" }
}

""
"--- Scheduled defrag task ---"
$task = Get-ScheduledTask -TaskName 'ScheduledDefrag' -ErrorAction SilentlyContinue
if ($task) {
    $info = $task | Get-ScheduledTaskInfo
    "ScheduledDefrag [$($task.State)] last run $($info.LastRunTime) result $($info.LastTaskResult)"
} else { "No ScheduledDefrag task registered." }""",
    },
    {
        "key": "system-file-check",
        "title": "System file check (SFC)",
        "group": "Services",
        "field": "other_observations",
        "summary": "Runs sfc /scannow and extracts the corruption and repair lines from CBS.log.",
        "body": """\
$start = Get-Date
"Running sfc /scannow - this takes several minutes."
sfc /scannow | Out-Host

$entries = Get-Content "$env:windir\\Logs\\CBS\\CBS.log" |
    Where-Object {
        $_ -match '\\[SR\\]' -and
        $_.Length -ge 19 -and
        $_.Substring(0, 19) -ge $start.ToString('yyyy-MM-dd HH:mm:ss')
    }

"--- CORRUPTION / FAILED REPAIR ENTRIES ---"
$bad = $entries | Select-String -Pattern 'Cannot repair|corrupted|could not reproject' |
    ForEach-Object { $_.Line }
if ($bad) { $bad } else { "None." }

""
"--- FILE REPAIR ENTRIES ---"
$fixed = $entries | Select-String -Pattern 'Repairing corrupted file|Repaired file' |
    ForEach-Object { $_.Line }
if ($fixed) { $fixed } else { "None." }""",
    },
]


def script_groups() -> list[dict]:
    """The scripts arranged under their form section, ready for the page.

    Each entry carries the rendered PowerShell and the label of the field it
    fills, so the template does no work beyond displaying them.
    """
    groups: list[dict] = []
    for script in MAINTENANCE_SCRIPTS:
        group = next((g for g in groups if g["title"] == script["group"]), None)
        if group is None:
            group = {"title": script["group"], "scripts": []}
            groups.append(group)
        group["scripts"].append(
            {
                **script,
                "powershell": powershell_file(script),
                "field_label": field_label(script["field"]),
            }
        )
    return groups


def find_script(key: str) -> dict | None:
    return next((s for s in MAINTENANCE_SCRIPTS if s["key"] == key), None)


def powershell_file(script: dict) -> str:
    """The .ps1 exactly as it is shown on the page and downloaded."""
    return _report(script["title"], script["body"])


def cmd_file(script: dict) -> str:
    """A .cmd that elevates, rebuilds the .ps1 in %TEMP%, and runs it.

    The PowerShell travels as base64 so quoting, redirection, and percent signs
    survive the batch parser intact.
    """
    payload = base64.b64encode(powershell_file(script).encode("utf-8")).decode("ascii")
    chunks = [payload[index : index + 200] for index in range(0, len(payload), 200)]
    name = script["key"]

    lines = [
        "@echo off",
        f":: {script['title']} - NGOB/ICT/104b maintenance report helper",
        ":: Elevates, writes the PowerShell script to %TEMP%, and runs it.",
        "",
        ":: --- Run elevated ---",
        "net session >nul 2>&1",
        "if %errorlevel% neq 0 (",
        "    powershell -NoProfile -Command \"Start-Process -FilePath '%~f0' -Verb RunAs\"",
        "    exit /b",
        ")",
        "",
        "setlocal",
        f'set "B64=%TEMP%\\{name}.b64"',
        f'set "PS1=%TEMP%\\{name}.ps1"',
        'if exist "%B64%" del "%B64%"',
        "",
    ]
    lines += [f'>>"%B64%" echo {chunk}' for chunk in chunks]
    lines += [
        "",
        'powershell -NoProfile -Command "[IO.File]::WriteAllBytes($env:PS1,'
        " [Convert]::FromBase64String(((Get-Content $env:B64) -join '')))\"",
        'powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"',
        'del "%B64%"',
        "endlocal",
    ]
    return "\r\n".join(lines) + "\r\n"
