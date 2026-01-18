# DocWire Uninstaller for Windows
# Run: .\uninstall.ps1

$ErrorActionPreference = "Stop"

Write-Host "DocWire Uninstaller (Windows)" -ForegroundColor Cyan
Write-Host "=" * 40

$installDir = Join-Path $env:USERPROFILE "bin\docwire"

# Stop running watchers first
$registryFile = Join-Path $installDir "dw-registry.txt"
if (Test-Path $registryFile) {
    Write-Host "Stopping running watchers..."
    $content = Get-Content $registryFile -Raw
    if ($content -match '=x=\s*watchers;([^=]*?);\s*=z=') {
        $raw = $matches[1].Trim()
        $parts = $raw.Split('|') | Where-Object { $_ }
        for ($i = 1; $i -lt $parts.Count - 1; $i += 3) {
            $procId = $parts[$i]
            taskkill /PID $procId /F 2>$null | Out-Null
        }
    }
    Write-Host "Watchers stopped"
}

# Remove files
if (Test-Path $installDir) {
    Remove-Item -Path $installDir -Recurse -Force
    Write-Host "Removed: $installDir" -ForegroundColor Green
} else {
    Write-Host "Not installed: $installDir not found"
}

# Remove from PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -like "*$installDir*") {
    $newPath = ($currentPath -split ';' | Where-Object { $_ -ne $installDir }) -join ';'
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Removed from PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "=" * 40
Write-Host "Uninstall complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Note: .dw/ folders in your project folders are NOT removed."
Write-Host "Delete them manually with: Remove-Item -Recurse .dw"
Write-Host ""
