# AI Trip Checklist API Deployment Script for Windows
# PowerShell version of the deployment script

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "rollback", "status", "backup", "help")]
    [string]$Command = "deploy"
)

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$BackupDir = Join-Path $ProjectDir "backups"
$LogFile = Join-Path $ProjectDir "logs\deploy.log"

# Ensure logs directory exists
$LogsDir = Join-Path $ProjectDir "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# Logging functions
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$Level] $Message"
    
    switch ($Level) {
        "ERROR" { Write-Host $LogMessage -ForegroundColor Red }
        "SUCCESS" { Write-Host $LogMessage -ForegroundColor Green }
        "WARNING" { Write-Host $LogMessage -ForegroundColor Yellow }
        default { Write-Host $LogMessage -ForegroundColor Blue }
    }
    
    Add-Content -Path $LogFile -Value $LogMessage
}

function Write-Error-Log {
    param([string]$Message)
    Write-Log $Message "ERROR"
}

function Write-Success-Log {
    param([string]$Message)
    Write-Log $Message "SUCCESS"
}

function Write-Warning-Log {
    param([string]$Message)
    Write-Log $Message "WARNING"
}

# Check prerequisites
function Test-Prerequisites {
    Write-Log "Checking prerequisites..."
    
    # Check if Docker is installed and running
    try {
        $null = docker --version
        $null = docker info
    }
    catch {
        Write-Error-Log "Docker is not installed or not running"
        exit 1
    }
    
    # Check if Docker Compose is installed
    try {
        $null = docker-compose --version
    }
    catch {
        Write-Error-Log "Docker Compose is not installed"
        exit 1
    }
    
    # Check if .env file exists
    $EnvFile = Join-Path $ProjectDir ".env"
    if (-not (Test-Path $EnvFile)) {
        Write-Error-Log ".env file not found. Please create it from .env.example"
        exit 1
    }
    
    # Check required environment variables
    $EnvContent = Get-Content $EnvFile | Where-Object { $_ -match "^[^#].*=" }
    $EnvVars = @{}
    foreach ($line in $EnvContent) {
        $parts = $line -split "=", 2
        if ($parts.Length -eq 2) {
            $EnvVars[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    
    if (-not $EnvVars.ContainsKey("GROQ_API_KEY") -or [string]::IsNullOrEmpty($EnvVars["GROQ_API_KEY"])) {
        Write-Error-Log "GROQ_API_KEY is not set in .env file"
        exit 1
    }
    
    if (-not $EnvVars.ContainsKey("SECRET_KEY") -or [string]::IsNullOrEmpty($EnvVars["SECRET_KEY"])) {
        Write-Error-Log "SECRET_KEY is not set in .env file"
        exit 1
    }
    
    Write-Success-Log "Prerequisites check passed"
}

# Setup directories
function Initialize-Directories {
    Write-Log "Setting up directories..."
    
    $Directories = @(
        (Join-Path $ProjectDir "logs"),
        (Join-Path $ProjectDir "data"),
        $BackupDir,
        (Join-Path $ProjectDir "ssl")
    )
    
    foreach ($dir in $Directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    Write-Success-Log "Directories created"
}

# Create backup
function New-Backup {
    Write-Log "Creating backup of current deployment..."
    
    $BackupName = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    $BackupPath = Join-Path $BackupDir $BackupName
    
    New-Item -ItemType Directory -Path $BackupPath -Force | Out-Null
    
    # Backup configuration files
    $EnvFile = Join-Path $ProjectDir ".env"
    if (Test-Path $EnvFile) {
        Copy-Item $EnvFile $BackupPath
    }
    
    # Backup data directory
    $DataDir = Join-Path $ProjectDir "data"
    if (Test-Path $DataDir) {
        Copy-Item $DataDir $BackupPath -Recurse
    }
    
    # Backup logs
    $LogsDir = Join-Path $ProjectDir "logs"
    if (Test-Path $LogsDir) {
        Copy-Item $LogsDir $BackupPath -Recurse
    }
    
    $BackupName | Out-File -FilePath (Join-Path $ProjectDir ".last_backup") -Encoding UTF8
    Write-Success-Log "Backup created: $BackupName"
}

# Build Docker images
function Build-Images {
    Write-Log "Building Docker images..."
    
    Push-Location $ProjectDir
    try {
        $result = docker-compose -f docker-compose.prod.yml build --no-cache
        if ($LASTEXITCODE -ne 0) {
            throw "Docker build failed"
        }
        Write-Success-Log "Docker images built successfully"
    }
    catch {
        Write-Error-Log "Failed to build Docker images: $_"
        exit 1
    }
    finally {
        Pop-Location
    }
}

# Run tests
function Invoke-Tests {
    Write-Log "Running tests..."
    
    Push-Location $ProjectDir
    try {
        $result = docker-compose -f docker-compose.prod.yml run --rm api python -m pytest tests/ -v
        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed"
        }
        Write-Success-Log "All tests passed"
    }
    catch {
        Write-Error-Log "Tests failed: $_"
        exit 1
    }
    finally {
        Pop-Location
    }
}

# Deploy application
function Start-Deployment {
    Write-Log "Deploying application..."
    
    Push-Location $ProjectDir
    try {
        # Stop existing containers
        docker-compose -f docker-compose.prod.yml down
        
        # Start new containers
        docker-compose -f docker-compose.prod.yml up -d
        
        # Wait for services to be healthy
        Write-Log "Waiting for services to be healthy..."
        $MaxAttempts = 30
        $Attempt = 1
        
        while ($Attempt -le $MaxAttempts) {
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8000/health/ready" -UseBasicParsing -TimeoutSec 5
                if ($response.StatusCode -eq 200) {
                    Write-Success-Log "Application is healthy and ready"
                    break
                }
            }
            catch {
                # Continue trying
            }
            
            if ($Attempt -eq $MaxAttempts) {
                Write-Error-Log "Application failed to become healthy within timeout"
                Invoke-Rollback
                exit 1
            }
            
            Write-Log "Attempt $Attempt/$MaxAttempts - waiting for application to be ready..."
            Start-Sleep -Seconds 10
            $Attempt++
        }
        
        Write-Success-Log "Deployment completed successfully"
    }
    catch {
        Write-Error-Log "Deployment failed: $_"
        exit 1
    }
    finally {
        Pop-Location
    }
}

# Rollback deployment
function Invoke-Rollback {
    Write-Error-Log "Rolling back to previous version..."
    
    $LastBackupFile = Join-Path $ProjectDir ".last_backup"
    if (-not (Test-Path $LastBackupFile)) {
        Write-Error-Log "No backup found for rollback"
        return
    }
    
    $BackupName = Get-Content $LastBackupFile -Raw | ForEach-Object { $_.Trim() }
    $BackupPath = Join-Path $BackupDir $BackupName
    
    if (-not (Test-Path $BackupPath)) {
        Write-Error-Log "Backup directory not found: $BackupPath"
        return
    }
    
    Push-Location $ProjectDir
    try {
        # Stop current containers
        docker-compose -f docker-compose.prod.yml down
        
        # Restore backup
        $BackupEnvFile = Join-Path $BackupPath ".env"
        if (Test-Path $BackupEnvFile) {
            Copy-Item $BackupEnvFile $ProjectDir
        }
        
        $BackupDataDir = Join-Path $BackupPath "data"
        if (Test-Path $BackupDataDir) {
            $ProjectDataDir = Join-Path $ProjectDir "data"
            if (Test-Path $ProjectDataDir) {
                Remove-Item $ProjectDataDir -Recurse -Force
            }
            Copy-Item $BackupDataDir $ProjectDir -Recurse
        }
        
        # Start containers with previous configuration
        docker-compose -f docker-compose.prod.yml up -d
        
        Write-Warning-Log "Rollback completed"
    }
    finally {
        Pop-Location
    }
}

# Cleanup old backups
function Remove-OldBackups {
    Write-Log "Cleaning up old backups..."
    
    if (Test-Path $BackupDir) {
        $Backups = Get-ChildItem $BackupDir | Sort-Object CreationTime -Descending
        if ($Backups.Count -gt 5) {
            $BackupsToRemove = $Backups | Select-Object -Skip 5
            foreach ($backup in $BackupsToRemove) {
                Remove-Item $backup.FullName -Recurse -Force
            }
        }
    }
    
    Write-Success-Log "Old backups cleaned up"
}

# Show deployment status
function Show-Status {
    Write-Log "Deployment Status:"
    Write-Host "===================="
    
    Push-Location $ProjectDir
    try {
        docker-compose -f docker-compose.prod.yml ps
        
        Write-Host ""
        Write-Log "Application Health:"
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
            $healthData = $response.Content | ConvertFrom-Json
            $healthData | ConvertTo-Json -Depth 10
            Write-Success-Log "Health check passed"
        }
        catch {
            Write-Warning-Log "Health check failed: $_"
        }
    }
    finally {
        Pop-Location
    }
}

# Main deployment function
function Start-MainDeployment {
    Write-Log "Starting deployment of AI Trip Checklist API"
    
    Test-Prerequisites
    Initialize-Directories
    New-Backup
    Build-Images
    Invoke-Tests
    Start-Deployment
    Remove-OldBackups
    Show-Status
    
    Write-Success-Log "Deployment completed successfully!"
    Write-Log "Application is running at http://localhost:8000"
    Write-Log "Health check: http://localhost:8000/health"
    Write-Log "API documentation: http://localhost:8000/docs (if enabled)"
}

# Handle script commands
switch ($Command) {
    "deploy" {
        Start-MainDeployment
    }
    "rollback" {
        Invoke-Rollback
    }
    "status" {
        Show-Status
    }
    "backup" {
        New-Backup
    }
    "help" {
        Write-Host "Usage: .\deploy.ps1 [deploy|rollback|status|backup|help]"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  deploy   - Deploy the application (default)"
        Write-Host "  rollback - Rollback to previous version"
        Write-Host "  status   - Show deployment status"
        Write-Host "  backup   - Create backup of current deployment"
        Write-Host "  help     - Show this help message"
    }
    default {
        Write-Error-Log "Unknown command: $Command"
        Write-Host "Use '.\deploy.ps1 help' for usage information"
        exit 1
    }
}