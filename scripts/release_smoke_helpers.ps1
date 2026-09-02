Set-StrictMode -Version Latest

function Invoke-FrozenSmokeProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExePath,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [ValidateRange(10, 600)]
        [int]$TimeoutSeconds = 120,

        [string]$FailureLabel = "Frozen executable smoke"
    )

    $resolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
    $resolvedWorkingDirectory = (Resolve-Path -LiteralPath $WorkingDirectory).Path
    $process = Start-Process `
        -FilePath $resolvedExe `
        -ArgumentList "--smoke-exit" `
        -WorkingDirectory $resolvedWorkingDirectory `
        -PassThru

    try {
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force
                $process.WaitForExit()
            }
            throw "$FailureLabel timed out after $TimeoutSeconds seconds (pid=$($process.Id), exe=$resolvedExe)"
        }
        if ($process.ExitCode -ne 0) {
            throw "$FailureLabel failed with exit code $($process.ExitCode)"
        }
        return $process.ExitCode
    } finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
        $process.Dispose()
    }
}
