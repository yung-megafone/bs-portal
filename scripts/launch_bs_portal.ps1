param(
    [switch]$NoBrowser,
    [string]$Bind = "127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Message) {
    Write-Host "[BS Portal] $Message" -ForegroundColor Cyan
}

function Get-DotEnvValue([string]$Path, [string]$Name) {
    $match = Get-Content -LiteralPath $Path | Where-Object {
        $_ -match "^\s*$([regex]::Escape($Name))\s*="
    } | Select-Object -Last 1

    if ($null -eq $match) {
        return $null
    }

    $value = ($match -split "=", 2)[1].Trim()
    if (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

try {
    $ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDirectory "..")).Path
    $VenvDirectory = Join-Path $ProjectRoot ".venv"
    $VenvPython = Join-Path $VenvDirectory "Scripts\python.exe"
    $Requirements = Join-Path $ProjectRoot "requirements.txt"
    $RequirementsStamp = Join-Path $VenvDirectory ".requirements.sha256"
    $ManagePy = Join-Path $ProjectRoot "portal\manage.py"
    $EnvFile = Join-Path $ProjectRoot ".env"
    $EnvExample = Join-Path $ProjectRoot ".env.example"

    Push-Location $ProjectRoot
    try {
        Write-Step "Project root: $ProjectRoot"

        if (-not (Test-Path -LiteralPath $ManagePy)) {
            throw "portal\manage.py was not found. Run the launcher from an intact B.S. Portal checkout."
        }
        if (-not (Test-Path -LiteralPath $Requirements)) {
            throw "requirements.txt was not found."
        }

        if (-not (Test-Path -LiteralPath $VenvPython)) {
            Write-Step "Creating Python 3.11 virtual environment..."
            $PyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
            if ($null -eq $PyLauncher) {
                throw "Python Launcher (py.exe) was not found. Install Python 3.11 for Windows and enable the launcher."
            }
            & py.exe -3.11 -m venv $VenvDirectory
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
                throw "Python 3.11 virtual environment creation failed."
            }
        }

        $PythonVersion = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -ne 0) {
            throw "The virtual-environment Python executable could not be started."
        }
        if ($PythonVersion.Trim() -ne "3.11") {
            throw "Existing .venv uses Python $($PythonVersion.Trim()), but this repository targets Python 3.11. Remove .venv and relaunch to rebuild it."
        }

        $RequirementsHash = (Get-FileHash -LiteralPath $Requirements -Algorithm SHA256).Hash
        $InstalledHash = if (Test-Path -LiteralPath $RequirementsStamp) {
            (Get-Content -LiteralPath $RequirementsStamp -Raw).Trim()
        } else {
            ""
        }

        if ($InstalledHash -ne $RequirementsHash) {
            Write-Step "Installing/updating Python dependencies because requirements.txt changed or has not been recorded for this venv..."
            & $VenvPython -m pip install -r $Requirements
            if ($LASTEXITCODE -ne 0) {
                throw "Dependency installation failed."
            }
            Set-Content -LiteralPath $RequirementsStamp -Value $RequirementsHash -Encoding ascii
        } else {
            Write-Step "Dependencies already match requirements.txt."
        }

        if (-not (Test-Path -LiteralPath $EnvFile)) {
            if (-not (Test-Path -LiteralPath $EnvExample)) {
                throw ".env is missing and .env.example is also missing. Create a local .env with the MYSQL_* settings required by portal/config/settings/base.py."
            }
            Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
            throw "Created .env from .env.example. Edit the local MySQL credentials, then launch again. Nothing was migrated or started."
        }

        Write-Step "Validating local environment configuration..."
        foreach ($Name in @("MYSQL_DATABASE", "MYSQL_USER", "MYSQL_HOST", "MYSQL_PORT")) {
            $Value = Get-DotEnvValue -Path $EnvFile -Name $Name
            if ([string]::IsNullOrWhiteSpace($Value)) {
                throw ".env must define $Name before the portal can start."
            }
        }

        $Password = Get-DotEnvValue -Path $EnvFile -Name "MYSQL_PASSWORD"
        if ($null -eq $Password) {
            throw ".env must contain MYSQL_PASSWORD (an empty local password is allowed only if that is intentionally how your MySQL user is configured)."
        }
        if ($Password -eq "CHANGE_ME") {
            throw "MYSQL_PASSWORD is still the .env.example placeholder. Edit .env before starting the portal."
        }

        Write-Step "Running Django system checks (safe; no schema changes)..."
        & $VenvPython $ManagePy check --settings=config.settings.local
        if ($LASTEXITCODE -ne 0) {
            throw "Django system checks failed."
        }

        Write-Step "Checking for pending migrations (safe; migrate --check does not apply them)..."
        & $VenvPython $ManagePy migrate --check --settings=config.settings.local
        if ($LASTEXITCODE -ne 0) {
            Write-Host "" 
            Write-Host "Pending migrations or a database connectivity/configuration problem was detected." -ForegroundColor Yellow
            Write-Host "No migrations were applied. Current migration plan:" -ForegroundColor Yellow
            & $VenvPython $ManagePy showmigrations --plan --settings=config.settings.local
            Write-Host ""
            Write-Host "When you are ready to apply reviewed migrations manually:" -ForegroundColor Yellow
            Write-Host "  .\.venv\Scripts\python.exe portal\manage.py migrate --settings=config.settings.local"
            throw "Startup stopped before runserver because the database/migration check did not pass."
        }

        Write-Step "Database is reachable and no migrations are pending."
        Write-Step "Running one BAM automation pulse (safe operational catch-up)..."
        & $VenvPython $ManagePy process_bam_automation --settings=config.settings.local
        if ($LASTEXITCODE -ne 0) {
            Write-Host "BAM automation pulse failed; continuing to runserver so the portal remains available." -ForegroundColor Yellow
        }
        $UrlHost = ($Bind -split ":", 2)[0]
        $UrlPort = if ($Bind -match ":(\d+)$") { $Matches[1] } else { "8000" }
        if ($UrlHost -eq "0.0.0.0") {
            $UrlHost = "127.0.0.1"
        }
        $Url = "http://${UrlHost}:${UrlPort}/"

        if (-not $NoBrowser) {
            Write-Step "Browser will open at $Url once runserver is starting."
            Start-Job -ScriptBlock {
                param($TargetUrl)
                Start-Sleep -Milliseconds 1200
                Start-Process $TargetUrl
            } -ArgumentList $Url | Out-Null
        }

        Write-Step "Starting Django development server on $Bind"
        Write-Host "Press Ctrl+C to stop the local server."
        & $VenvPython $ManagePy runserver $Bind --settings=config.settings.local
        if ($LASTEXITCODE -ne 0) {
            throw "Django development server exited with code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
catch {
    Write-Host ""
    Write-Host "B.S. Portal launcher error:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
