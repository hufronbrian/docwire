# DocWire Uninstaller for Windows
# Run: .\uninstall.ps1

$ErrorActionPreference = "Stop"

Write-Host "DocWire Uninstaller (Windows)" -ForegroundColor Cyan
Write-Host "=" * 40

$installDir = Join-Path $env:USERPROFILE "bin\docwire"

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
