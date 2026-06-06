param(
    [string]$DestinationRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $DestinationRoot = Join-Path $repoRoot "data_backups"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $DestinationRoot $timestamp

$databases = @(
    @{
        Label = "SQE DailyWork sqe_v2.db"
        Source = Join-Path $repoRoot "data\sqe_v2.db"
        Target = "sqe_v2.db"
    }
)

$optionalDatabases = @(
    @{
        Label = "Archived NCR defect.db"
        Source = Join-Path $repoRoot "ncr\data\defect.db.migrated"
        Target = "ncr_defect.db.migrated"
    }
)

$missing = @()
foreach ($db in $databases) {
    if (-not (Test-Path -LiteralPath $db.Source -PathType Leaf)) {
        $missing += "$($db.Label): $($db.Source)"
    }
}

if ($missing.Count -gt 0) {
    throw "Required database file(s) missing:`n$($missing -join "`n")"
}

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$results = @()
foreach ($db in @($databases + $optionalDatabases)) {
    if (-not (Test-Path -LiteralPath $db.Source -PathType Leaf)) {
        if ($databases -contains $db) {
            throw "Required database file missing: $($db.Source)"
        }
        continue
    }
    $targetPath = Join-Path $backupDir $db.Target
    Copy-Item -LiteralPath $db.Source -Destination $targetPath -Force
    $item = Get-Item -LiteralPath $targetPath
    $results += [pscustomobject]@{
        Label = $db.Label
        Source = $db.Source
        Backup = $targetPath
        Length = $item.Length
        LastWriteTime = $item.LastWriteTime
    }
}

Write-Host "Backup complete: $backupDir"
$results | Format-Table -AutoSize
