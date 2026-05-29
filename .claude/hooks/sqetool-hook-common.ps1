Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-SqetoolHookInput {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [pscustomobject]@{ _raw = "" }
    }

    try {
        $parsed = $raw | ConvertFrom-Json
        $parsed | Add-Member -NotePropertyName "_raw" -NotePropertyValue $raw -Force
        return $parsed
    } catch {
        return [pscustomobject]@{ _raw = $raw }
    }
}

function Get-SqetoolNestedProperty {
    param(
        [object]$Object,
        [string]$Path
    )

    $current = $Object
    foreach ($segment in $Path.Split(".")) {
        if ($null -eq $current) {
            return $null
        }
        $prop = $current.PSObject.Properties[$segment]
        if ($null -eq $prop) {
            return $null
        }
        $current = $prop.Value
    }
    return $current
}

function ConvertTo-SqetoolText {
    param([object]$Value)

    if ($null -eq $Value) {
        return ""
    }
    if ($Value -is [string]) {
        return $Value
    }
    try {
        return ($Value | ConvertTo-Json -Depth 80 -Compress)
    } catch {
        return [string]$Value
    }
}

function ConvertTo-SqetoolJson {
    param([object]$Value)
    return ($Value | ConvertTo-Json -Depth 20 -Compress)
}

function Write-SqetoolSystemMessage {
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message)) {
        return
    }
    ConvertTo-SqetoolJson ([pscustomobject]@{ systemMessage = $Message }) | Write-Output
}

function Write-SqetoolBlock {
    param([string]$Reason)
    ConvertTo-SqetoolJson ([pscustomobject]@{
        decision = "block"
        reason = $Reason
        systemMessage = $Reason
    }) | Write-Output
    exit 0
}

function Get-SqetoolCommandText {
    param([object]$HookInput)

    $parts = [System.Collections.Generic.List[string]]::new()
    foreach ($path in @("tool_input.command", "tool_input.cmd", "tool_input.args", "command", "cmd")) {
        $value = Get-SqetoolNestedProperty -Object $HookInput -Path $path
        if ($null -ne $value) {
            $parts.Add((ConvertTo-SqetoolText $value)) | Out-Null
        }
    }

    if ($parts.Count -eq 0) {
        $parts.Add((ConvertTo-SqetoolText $HookInput)) | Out-Null
    }
    return ($parts -join " ")
}
