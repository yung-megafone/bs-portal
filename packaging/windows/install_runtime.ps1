param(
    [Parameter(Mandatory = $true)][string]$AppDir,
    [Parameter(Mandatory = $true)][string]$DataDir,
    [Parameter(Mandatory = $true)][string]$AppExe,
    [string]$MySqlVersion = "8.4.11",
    [int]$MySqlPort = 33069,
    [string]$ServiceName = "BSPortalMySQL",
    [string]$BundledMySqlZip = "",
    [string]$BundledVcRedist = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$MySqlUrl = "https://dev.mysql.com/get/Downloads/MySQL-8.4/mysql-$MySqlVersion-winx64.zip"
$MySql8411Md5 = "2e833921898a9a030ea6bfe81bd811bc"
$VcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

function Write-Step([string]$Message) {
    Write-Host "[B.S. Portal Setup] $Message" -ForegroundColor Cyan
}

function New-HexSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    }
    finally {
        $rng.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Protect-MachineString([string]$Value) {
    Add-Type -AssemblyName System.Security
    $plain = [Text.Encoding]::UTF8.GetBytes($Value)
    $protected = [Security.Cryptography.ProtectedData]::Protect(
        $plain,
        $null,
        [Security.Cryptography.DataProtectionScope]::LocalMachine
    )
    return [Convert]::ToBase64String($protected)
}

function Unprotect-MachineString([string]$Value) {
    Add-Type -AssemblyName System.Security
    $protected = [Convert]::FromBase64String($Value)
    $plain = [Security.Cryptography.ProtectedData]::Unprotect(
        $protected,
        $null,
        [Security.Cryptography.DataProtectionScope]::LocalMachine
    )
    return [Text.Encoding]::UTF8.GetString($plain)
}

function Ensure-Directory([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-JsonAtomic([object]$Value, [string]$Path, [int]$Depth = 6) {
    $tempPath = "$Path.new"
    try {
        $Value | ConvertTo-Json -Depth $Depth | Set-Content -LiteralPath $tempPath -Encoding utf8
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    }
    finally {
        Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-Download([string]$Uri, [string]$Destination) {
    Write-Step "Downloading $Uri"
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $Uri -OutFile $Destination -UseBasicParsing
}

function Assert-MySqlArchive([string]$Path) {
    if ($MySqlVersion -eq "8.4.11") {
        $actual = (Get-FileHash -LiteralPath $Path -Algorithm MD5).Hash.ToLowerInvariant()
        if ($actual -ne $MySql8411Md5) {
            throw "MySQL archive integrity check failed. Expected MD5 $MySql8411Md5 but received $actual."
        }
    }
}

function Assert-MicrosoftSignature([string]$Path) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "Microsoft") {
        throw "The Visual C++ redistributable does not have a valid Microsoft Authenticode signature."
    }
}

function Test-VcRuntime {
    $key = "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
    try {
        $runtime = Get-ItemProperty -LiteralPath $key -ErrorAction Stop
        return ([int]$runtime.Installed -eq 1)
    }
    catch {
        return $false
    }
}

function Wait-Tcp([string]$HostName, [int]$Port, [int]$TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $client = [Net.Sockets.TcpClient]::new()
            $task = $client.ConnectAsync($HostName, $Port)
            if ($task.Wait(750) -and $client.Connected) {
                $client.Dispose()
                return $true
            }
            $client.Dispose()
        }
        catch {}
        Start-Sleep -Milliseconds 400
    }
    return $false
}

Ensure-Directory $DataDir
$LogsDir = Join-Path $DataDir "logs"
$BackupsDir = Join-Path $DataDir "backups"
$MediaDir = Join-Path $DataDir "media"
$MySqlDataDir = Join-Path $DataDir "mysql-data"
$DownloadsDir = Join-Path $DataDir "install-cache"
foreach ($dir in @($LogsDir, $BackupsDir, $MediaDir, $DownloadsDir)) { Ensure-Directory $dir }

$TranscriptStarted = $false
$TranscriptPath = Join-Path $LogsDir ("setup-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
try {
    Start-Transcript -LiteralPath $TranscriptPath -Append | Out-Null
    $TranscriptStarted = $true
}
catch {
    Write-Warning "Could not start setup transcript logging: $($_.Exception.Message)"
}

# MySQL 8.4 requires the Microsoft VC++ 2019+ runtime. The evergreen VS 2015-2022
# redistributable uses the same x64 runtime registry family.
if (-not (Test-VcRuntime)) {
    $VcInstaller = $BundledVcRedist
    if ([string]::IsNullOrWhiteSpace($VcInstaller) -or -not (Test-Path -LiteralPath $VcInstaller)) {
        $VcInstaller = Join-Path $DownloadsDir "vc_redist.x64.exe"
        if (-not (Test-Path -LiteralPath $VcInstaller)) {
            Invoke-Download $VcRedistUrl $VcInstaller
        }
    }
    Assert-MicrosoftSignature $VcInstaller
    Write-Step "Installing Microsoft Visual C++ runtime required by MySQL..."
    $vc = Start-Process -FilePath $VcInstaller -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru
    if ($vc.ExitCode -notin @(0, 1638, 3010)) {
        throw "Visual C++ redistributable installer exited with code $($vc.ExitCode)."
    }
}
else {
    Write-Step "Microsoft Visual C++ x64 runtime already installed."
}

$MySqlRoot = Join-Path $AppDir "mysql"
$MySqlBin = Join-Path $MySqlRoot "bin"
$Mysqld = Join-Path $MySqlBin "mysqld.exe"
$MysqlClient = Join-Path $MySqlBin "mysql.exe"
$RuntimeConfig = Join-Path $DataDir "runtime.json"
$RootRecovery = Join-Path $DataDir "mysql-root.json"
$MyIni = Join-Path $DataDir "my.ini"

if (Test-Path -LiteralPath $RuntimeConfig) {
    try {
        $ExistingRuntime = Get-Content -LiteralPath $RuntimeConfig -Raw | ConvertFrom-Json
        if ($null -ne $ExistingRuntime.database.port) { $MySqlPort = [int]$ExistingRuntime.database.port }
        if (-not [string]::IsNullOrWhiteSpace([string]$ExistingRuntime.mysql.service_name)) {
            $ServiceName = [string]$ExistingRuntime.mysql.service_name
        }
    }
    catch {
        throw "Existing runtime.json could not be parsed: $($_.Exception.Message)"
    }
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $Mysqld)) {
    Write-Step "Preparing private MySQL $MySqlVersion runtime..."
    $zip = $BundledMySqlZip
    if ([string]::IsNullOrWhiteSpace($zip) -or -not (Test-Path -LiteralPath $zip)) {
        $zip = Join-Path $DownloadsDir "mysql-$MySqlVersion-winx64.zip"
        if (-not (Test-Path -LiteralPath $zip)) {
            Invoke-Download $MySqlUrl $zip
        }
    }

    Assert-MySqlArchive $zip
    $extractRoot = Join-Path $env:TEMP ("bs-portal-mysql-" + [guid]::NewGuid().ToString("N"))
    Ensure-Directory $extractRoot
    try {
        Expand-Archive -LiteralPath $zip -DestinationPath $extractRoot -Force
        $candidate = Get-ChildItem -LiteralPath $extractRoot -Directory | Where-Object {
            Test-Path -LiteralPath (Join-Path $_.FullName "bin\mysqld.exe")
        } | Select-Object -First 1
        if ($null -eq $candidate) {
            throw "The downloaded MySQL archive did not contain bin\mysqld.exe."
        }
        if (Test-Path -LiteralPath $MySqlRoot) {
            Remove-Item -LiteralPath $MySqlRoot -Recurse -Force
        }
        Move-Item -LiteralPath $candidate.FullName -Destination $MySqlRoot
    }
    finally {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $Mysqld) -or -not (Test-Path -LiteralPath $MysqlClient)) {
    throw "The private MySQL runtime is incomplete."
}

$baseIni = $MySqlRoot.Replace("\\", "/")
$dataIni = $MySqlDataDir.Replace("\\", "/")
$logIni = (Join-Path $LogsDir "mysql-error.log").Replace("\\", "/")
@"
[mysqld]
basedir="$baseIni"
datadir="$dataIni"
port=$MySqlPort
bind-address=127.0.0.1
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci
skip-log-bin
log-error="$logIni"

[client]
host=127.0.0.1
port=$MySqlPort
protocol=tcp
default-character-set=utf8mb4
"@ | Set-Content -LiteralPath $MyIni -Encoding ascii

Ensure-Directory $MySqlDataDir
& icacls.exe $MySqlDataDir /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null

$ExistingData = Test-Path -LiteralPath (Join-Path $MySqlDataDir "mysql")
if (-not $ExistingData) {
    if (Test-Path -LiteralPath $RuntimeConfig) {
        throw "runtime.json exists but the private MySQL data directory is missing. Restore the database or remove the stale runtime configuration before reinstalling."
    }
    Write-Step "Initializing B.S. Portal MySQL data directory..."
    & $Mysqld "--defaults-file=$MyIni" --initialize-insecure --console
    if ($LASTEXITCODE -ne 0) { throw "MySQL data-directory initialization failed." }
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($null -ne $service) {
    $serviceConfig = (& sc.exe qc $ServiceName | Out-String)
    $expectedExe = [Regex]::Escape($Mysqld)
    if ($serviceConfig -notmatch $expectedExe) {
        Write-Step "Repairing MySQL service executable path for this installation..."
        if ($service.Status -ne "Stopped") {
            Stop-Service -Name $ServiceName -Force
        }
        & sc.exe delete $ServiceName | Out-Null
        Start-Sleep -Milliseconds 500
        $service = $null
    }
}

if ($null -eq $service) {
    Write-Step "Installing private MySQL Windows service..."
    & $Mysqld --install $ServiceName "--defaults-file=$MyIni"
    if ($LASTEXITCODE -ne 0) { throw "MySQL Windows service installation failed." }
    & sc.exe config $ServiceName start= auto | Out-Null
}

$service = Get-Service -Name $ServiceName -ErrorAction Stop
if ($service.Status -ne "Running") {
    Write-Step "Starting private MySQL service..."
    Start-Service -Name $ServiceName
}
if (-not (Wait-Tcp "127.0.0.1" $MySqlPort 35)) {
    throw "MySQL service did not become ready on 127.0.0.1:$MySqlPort. See $logIni"
}

if (-not (Test-Path -LiteralPath $RuntimeConfig)) {
    Write-Step "Generating isolated B.S. Portal database/application credentials..."
    $RootPassword = New-HexSecret 32
    $AppPassword = New-HexSecret 32
    $DjangoSecret = New-HexSecret 48

    $config = [ordered]@{
        schema_version = 1
        database = [ordered]@{
            name = "bsportal"
            user = "bsportal_app"
            password_dpapi = Protect-MachineString $AppPassword
            host = "127.0.0.1"
            port = $MySqlPort
        }
        django_secret_dpapi = Protect-MachineString $DjangoSecret
        mysql = [ordered]@{
            service_name = $ServiceName
            bin_dir = $MySqlBin
            version = $MySqlVersion
        }
        server = [ordered]@{
            host = "127.0.0.1"
            port = 8765
        }
    }
    # Write the administrator-only root recovery material first. If setup is
    # interrupted before runtime.json is committed, a retry can safely replace
    # this file while MySQL is still in its initialize-insecure state.
    $rootConfig = [ordered]@{ root_password_dpapi = Protect-MachineString $RootPassword }
    Write-JsonAtomic $rootConfig $RootRecovery 3
    & icacls.exe $RootRecovery /inheritance:r /grant:r "*S-1-5-18:F" "*S-1-5-32-544:F" | Out-Null

    Write-JsonAtomic $config $RuntimeConfig 5
    & icacls.exe $RuntimeConfig /inheritance:r /grant:r "*S-1-5-18:F" "*S-1-5-32-544:F" "*S-1-5-32-545:R" | Out-Null
}

$runtimeForProvisioning = Get-Content -LiteralPath $RuntimeConfig -Raw | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $RootRecovery)) {
    throw "The protected MySQL root recovery file is missing. Run database recovery before attempting an in-place repair."
}
$rootForProvisioning = Get-Content -LiteralPath $RootRecovery -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$rootForProvisioning.root_password_dpapi)) {
    throw "The MySQL root recovery file is invalid."
}
$RootPassword = Unprotect-MachineString ([string]$rootForProvisioning.root_password_dpapi)
$AppPassword = Unprotect-MachineString ([string]$runtimeForProvisioning.database.password_dpapi)

$sql = @"
ALTER USER 'root'@'localhost' IDENTIFIED BY '$RootPassword';
CREATE DATABASE IF NOT EXISTS bsportal CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'bsportal_app'@'127.0.0.1' IDENTIFIED BY '$AppPassword';
ALTER USER 'bsportal_app'@'127.0.0.1' IDENTIFIED BY '$AppPassword';
GRANT ALL PRIVILEGES ON bsportal.* TO 'bsportal_app'@'127.0.0.1';
FLUSH PRIVILEGES;
"@

function Invoke-RootProvisioning([string]$CurrentPassword) {
    $oldMysqlPwd = $env:MYSQL_PWD
    try {
        if ([string]::IsNullOrEmpty($CurrentPassword)) {
            Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
        }
        else {
            $env:MYSQL_PWD = $CurrentPassword
        }
        $sql | & $MysqlClient --protocol=tcp --host=127.0.0.1 --port=$MySqlPort --user=root 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        if ($null -eq $oldMysqlPwd) {
            Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
        }
        else {
            $env:MYSQL_PWD = $oldMysqlPwd
        }
    }
}

Write-Step "Verifying/repairing the B.S. Portal database and application user..."
if (-not (Invoke-RootProvisioning $RootPassword)) {
    # A first-install interruption can leave runtime.json written while root is
    # still passwordless. Retry once using the initialize-insecure state.
    if (-not (Invoke-RootProvisioning "")) {
        throw "Could not authenticate as the private MySQL root account to provision/repair the B.S. Portal database."
    }
}

# Keep installation-path metadata current across repair/reinstall operations.
$runtimeObject = Get-Content -LiteralPath $RuntimeConfig -Raw | ConvertFrom-Json
$runtimeObject.mysql.bin_dir = $MySqlBin
$runtimeObject.mysql.service_name = $ServiceName
$runtimeObject.mysql.version = $MySqlVersion
$runtimeObject.database.port = $MySqlPort
Write-JsonAtomic $runtimeObject $RuntimeConfig 6
& icacls.exe $RuntimeConfig /inheritance:r /grant:r "*S-1-5-18:F" "*S-1-5-32-544:F" "*S-1-5-32-545:R" | Out-Null

# Media/backups/logs are application state and need ordinary local-user writes.
foreach ($dir in @($MediaDir, $BackupsDir, $LogsDir)) {
    & icacls.exe $dir /grant "*S-1-5-32-545:(OI)(CI)M" | Out-Null
}

Write-Step "Backing up and applying the release migration set..."
& $AppExe --maintenance backup-and-migrate
if ($LASTEXITCODE -ne 0) {
    throw "B.S. Portal database backup/migration failed. Existing data was not intentionally deleted; inspect $LogsDir and $BackupsDir."
}

if (Test-Path -LiteralPath $DownloadsDir) {
    Remove-Item -LiteralPath $DownloadsDir -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Step "Packaged runtime is ready."
if ($TranscriptStarted) {
    Stop-Transcript | Out-Null
}
