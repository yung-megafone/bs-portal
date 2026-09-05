param(
    [switch]$BundleDependencies,
    [switch]$SkipInstaller,
    [string]$PythonTag = "3.11"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Message) {
    Write-Host "[B.S. Portal Build] $Message" -ForegroundColor Cyan
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$BuildDir = Join-Path $Root ".build\windows"
$VenvDir = Join-Path $BuildDir "venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ScriptDir "requirements-build.txt"
$SpecFile = Join-Path $ScriptDir "BS-Portal.spec"
$IssFile = Join-Path $ScriptDir "BS-Portal.iss"
$DistDir = Join-Path $Root "dist\windows"
$ReleaseDir = Join-Path $Root "release\windows"
$StaticDir = Join-Path $Root ".desktop_staticfiles"
$VendorDir = Join-Path $ScriptDir "vendor"

foreach ($dir in @($BuildDir, $DistDir, $ReleaseDir, $VendorDir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Remove-Item -LiteralPath (Join-Path $ReleaseDir "BS-Portal-v0.2.0-alpha-Setup.exe") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $ReleaseDir "SHA256SUMS.txt") -Force -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Step "Creating isolated Python $PythonTag build environment..."
    $Py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -eq $Py) {
        throw "Python Launcher (py.exe) is required on the build machine. Install Python 3.11; release users do not need Python."
    }
    & py.exe "-$PythonTag" -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not create the build virtual environment." }
}

Write-Step "Installing Windows packaging dependencies..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) { throw "Packaging dependency installation failed." }

$env:DJANGO_SETTINGS_MODULE = "config.settings.desktop"
$env:DJANGO_SECRET_KEY = "build-only-secret-not-used-at-runtime"
$env:MYSQL_DATABASE = "bsportal"
$env:MYSQL_USER = "bsportal_app"
$env:MYSQL_PASSWORD = "build-only"
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "33069"
$env:BS_PORTAL_DATA_DIR = (Join-Path $BuildDir "runtime-data")

Write-Step "Validating desktop Django settings for PyInstaller..."
$PortalDir = Join-Path $Root "portal"
Push-Location $PortalDir
try {
    & $PythonExe -c "import django; django.setup(); from django.conf import settings; assert settings.ROOT_URLCONF == 'config.urls'; assert settings.WSGI_APPLICATION == 'config.wsgi.application'; print('Desktop settings OK:', settings.SETTINGS_MODULE)"
    if ($LASTEXITCODE -ne 0) { throw "Desktop Django settings preflight failed." }
}
finally {
    Pop-Location
}

if (Test-Path -LiteralPath $StaticDir) {
    Remove-Item -LiteralPath $StaticDir -Recurse -Force
}
Write-Step "Collecting production static files..."
& $PythonExe (Join-Path $Root "portal\manage.py") collectstatic --noinput --settings=config.settings.desktop
if ($LASTEXITCODE -ne 0) { throw "collectstatic failed." }

Write-Step "Building single-file BS-Portal.exe with PyInstaller..."
if (Test-Path -LiteralPath $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
}
& $PythonExe -m PyInstaller --noconfirm --clean --distpath $DistDir --workpath (Join-Path $BuildDir "pyinstaller") $SpecFile
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$Exe = Join-Path $DistDir "BS-Portal.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "PyInstaller completed without producing $Exe"
}

if ($BundleDependencies) {
    Write-Step "Downloading optional offline dependency payloads..."
    $ProgressPreference = "SilentlyContinue"
    $MySqlZip = Join-Path $VendorDir "mysql-8.4.11-winx64.zip"
    $VcRedist = Join-Path $VendorDir "vc_redist.x64.exe"
    if (-not (Test-Path -LiteralPath $MySqlZip)) {
        Invoke-WebRequest -Uri "https://dev.mysql.com/get/Downloads/MySQL-8.4/mysql-8.4.11-winx64.zip" -OutFile $MySqlZip -UseBasicParsing
    }
    if (-not (Test-Path -LiteralPath $VcRedist)) {
        Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile $VcRedist -UseBasicParsing
    }
    $mysqlMd5 = (Get-FileHash -LiteralPath $MySqlZip -Algorithm MD5).Hash.ToLowerInvariant()
    if ($mysqlMd5 -ne "2e833921898a9a030ea6bfe81bd811bc") {
        throw "Downloaded MySQL 8.4.11 ZIP failed the Oracle-published MD5 check."
    }
    $vcSignature = Get-AuthenticodeSignature -LiteralPath $VcRedist
    if ($vcSignature.Status -ne "Valid" -or $vcSignature.SignerCertificate.Subject -notmatch "Microsoft") {
        throw "Downloaded Visual C++ redistributable failed Authenticode verification."
    }
    Write-Warning "Bundling MySQL redistributes a third-party GPL component. Review its redistribution obligations before publishing the resulting installer."
}

if (-not $SkipInstaller) {
    $IsccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $IsccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($Iscc)) {
        $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if ($null -ne $Winget) {
            Write-Step "Inno Setup not found; installing build dependency with winget..."
            & winget.exe install --id JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements
            $Iscc = $IsccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }
    }
    if ([string]::IsNullOrWhiteSpace($Iscc)) {
        throw "Inno Setup 6 (ISCC.exe) is required to produce the single Setup.exe. BS-Portal.exe itself was built successfully."
    }

    Write-Step "Compiling single-file Windows installer..."
    $isccArguments = @()
    if ($BundleDependencies) {
        $isccArguments += "/DBundleMySql"
        $isccArguments += "/DBundleVcRedist"
    }
    $isccArguments += $IssFile
    & $Iscc @isccArguments
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
}

$Artifacts = Get-ChildItem -LiteralPath $ReleaseDir -Filter "*.exe" -ErrorAction SilentlyContinue
if ($SkipInstaller) {
    $Artifacts = @((Get-Item -LiteralPath $Exe))
}

$HashPath = Join-Path $ReleaseDir "SHA256SUMS.txt"
$hashLines = @()
foreach ($artifact in $Artifacts) {
    $hash = (Get-FileHash -LiteralPath $artifact.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashLines += "$hash  $($artifact.Name)"
}
$hashLines | Set-Content -LiteralPath $HashPath -Encoding ascii

Write-Host ""
Write-Step "Build complete."
foreach ($artifact in $Artifacts) {
    Write-Host "  $($artifact.FullName)"
}
Write-Host "  $HashPath"
