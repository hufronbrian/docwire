# DocWire Installer for Windows
# Run: .\install.ps1

$ErrorActionPreference = "Stop"

Write-Host "DocWire Installer (Windows)" -ForegroundColor Cyan
Write-Host "=" * 40

# Check Python
$hasPython = $false
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python") {
        $hasPython = $true
        Write-Host "Python: $pythonVersion"
    }
} catch {}

if (-not $hasPython) {
    Write-Host ""
    Write-Host "Python not found" -ForegroundColor Yellow
    Write-Host ""
    $choice = Read-Host "Open Python download page? [y/N]"
    if ($choice -eq "y" -or $choice -eq "Y") {
        Start-Process "https://www.python.org/downloads/"
        Write-Host ""
        Write-Host "Install Python 3.10+, then run this installer again"
    } else {
        Write-Host ""
        Write-Host "Install Python 3.10+ first:"
        Write-Host "  https://www.python.org/downloads/"
    }
    exit 1
}

# Check pip
$hasPip = $false
try {
    $pipVersion = pip --version 2>&1
    if ($pipVersion -match "pip") {
        $hasPip = $true
    }
} catch {}

if (-not $hasPip) {
    Write-Host ""
    Write-Host "pip not found" -ForegroundColor Yellow
    Write-Host ""
    $choice = Read-Host "Install pip now? [y/N]"
    if ($choice -eq "y" -or $choice -eq "Y") {
        python -m ensurepip --upgrade
    } else {
        Write-Host ""
        Write-Host "Install pip first:"
        Write-Host "  python -m ensurepip --upgrade"
        exit 1
    }
}

Write-Host "pip: OK"

# Check watchdog
Write-Host "Checking dependencies..."
$hasWatchdog = $false
try {
    python -c "import watchdog" 2>&1 | Out-Null
    $hasWatchdog = $true
} catch {}

if (-not $hasWatchdog) {
    Write-Host ""
    Write-Host "watchdog module not found" -ForegroundColor Yellow
    Write-Host ""
    $choice = Read-Host "Install watchdog now? [y/N]"
    if ($choice -eq "y" -or $choice -eq "Y") {
        pip install watchdog
    } else {
        Write-Host ""
        Write-Host "Install watchdog first:"
        Write-Host "  pip install watchdog"
        exit 1
    }
}

Write-Host "watchdog: OK"

# Set paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $scriptDir "win"
$installDir = Join-Path $env:USERPROFILE "bin\docwire"

# Check source exists
if (-not (Test-Path (Join-Path $sourceDir "dw.bat"))) {
    Write-Host "Error: win/dw.bat not found" -ForegroundColor Red
    exit 1
}

# Create install directory
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Write-Host "Created: $installDir"
} else {
    Write-Host "Updating existing installation..."
}

# Stop running watchers before update
$dwExe = Join-Path $installDir "dw.bat"
$watcherPaths = @()
if (Test-Path $dwExe) {
    Write-Host "Checking for running watchers..."
    $registryFile = Join-Path $installDir "dw-registry.txt"
    if (Test-Path $registryFile) {
        $content = Get-Content $registryFile -Raw
        # Parse DWML format to get watcher paths
        if ($content -match '=x=\s*watchers;([^=]*?);\s*=z=') {
            $raw = $matches[1].Trim()
            $parts = $raw.Split('|') | Where-Object { $_ }
            for ($i = 0; $i -lt $parts.Count - 2; $i += 3) {
                $watcherPaths += $parts[$i]
            }
        }
    }
    if ($watcherPaths.Count -gt 0) {
        Write-Host "Stopping $($watcherPaths.Count) watcher(s)..."
        # Use taskkill for each registered watcher PID
        $content = Get-Content $registryFile -Raw
        if ($content -match '=x=\s*watchers;([^=]*?);\s*=z=') {
            $raw = $matches[1].Trim()
            $parts = $raw.Split('|') | Where-Object { $_ }
            for ($i = 1; $i -lt $parts.Count - 1; $i += 3) {
                $procId = $parts[$i]
                taskkill /PID $procId /F 2>$null | Out-Null
            }
        }
        # Clear registry
        Set-Content -Path $registryFile -Value ""
        Write-Host "Watchers stopped"
    }
}

# Copy files (clean template first to remove legacy files)
Write-Host "Copying files..."
$templateDir = Join-Path $installDir "template"
if (Test-Path $templateDir) {
    Remove-Item -Path $templateDir -Recurse -Force
    Write-Host "Cleaned old template/"
}
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force
Write-Host "Copied win/ to $installDir"

# Add to PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$installDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$installDir", "User")
    Write-Host "Added to PATH: $installDir" -ForegroundColor Green
} else {
    Write-Host "Already in PATH"
}

Write-Host ""
Write-Host "=" * 40
Write-Host "Installation complete!" -ForegroundColor Green

# Auto-update all registered projects
$dwExe = Join-Path $installDir "dw.bat"
if (Test-Path $dwExe) {
    Write-Host ""
    Write-Host "Updating registered projects..."
    & $dwExe all update
}

# Notify user to restart watchers
if ($watcherPaths.Count -gt 0) {
    Write-Host ""
    Write-Host "NOTE: $($watcherPaths.Count) watcher(s) were stopped for update." -ForegroundColor Yellow
    Write-Host "Run 'dw all start' to restart them."
}

Write-Host ""
Write-Host "IMPORTANT: Restart your terminal for PATH changes to take effect"
Write-Host ""
Write-Host "Then test with:"
Write-Host "  dw"
Write-Host ""
Write-Host "To setup a docs folder:"
Write-Host "  cd your-docs-folder"
Write-Host "  dw setup"
Write-Host "  dw init"
Write-Host "  dw start"
Write-Host ""
