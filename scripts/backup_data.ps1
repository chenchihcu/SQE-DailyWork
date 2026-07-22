param(
    [string]$DestinationRoot,
    [string]$PythonExe
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python executable not found: $PythonExe"
}

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
    & $PythonExe (Join-Path $repoRoot "scripts\sqlite_backup.py") $db.Source $targetPath
    if ($LASTEXITCODE -ne 0) {
        throw "Verified SQLite backup failed: $($db.Source)"
    }
    $item = Get-Item -LiteralPath $targetPath
    $results += [pscustomobject]@{
        Label = $db.Label
        Source = $db.Source
        Backup = $targetPath
        Length = $item.Length
        LastWriteTime = $item.LastWriteTime
        Verified = $true
    }
}

Write-Host "Backup complete: $backupDir"
$results | Format-Table -AutoSize
