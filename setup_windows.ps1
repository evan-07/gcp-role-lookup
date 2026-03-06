# GCP Role Lookup - Windows Setup Helper
#
# Purpose: Validate prerequisites and set up GCP authentication on Windows.
# Usage: .\setup_windows.ps1
#
# This script will:
# 1. Check for Python 3.12+
# 2. Check for gcloud CLI
# 3. Guide you through gcloud auth application-default login
# 4. Create .env file template
# 5. Create virtual environment and install dependencies

param(
    [switch]$SkipGcloud = $false,
    [switch]$SkipVenv = $false
)

# Color output helpers
function Write-Success {
    Write-Host "[OK] $args" -ForegroundColor Green
}

function Write-Error_ {
    Write-Host "[ERROR] $args" -ForegroundColor Red
}

function Write-Warning_ {
    Write-Host "[WARNING] $args" -ForegroundColor Yellow
}

function Write-Info {
    Write-Host "[INFO] $args" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=== GCP Role Lookup - Windows Setup Helper ===" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Info "Checking Python 3.12+..."
$pythonVersion = & python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error_ "Python not found in PATH."
    Write-Info "Install from: https://www.python.org/downloads/"
    exit 1
}

# Parse version (e.g., "Python 3.12.1")
$versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
if ($versionMatch) {
    $major = [int]$matches[1]
    $minor = [int]$matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 12)) {
        Write-Error_ "Python $major.$minor found, but 3.12+ required."
        exit 1
    }
    Write-Success "Python $major.$minor found"
} else {
    Write-Error_ "Could not parse Python version: $pythonVersion"
    exit 1
}

# Check gcloud
if (-not $SkipGcloud) {
    Write-Info "Checking gcloud CLI..."
    
    # Try to find gcloud in common locations
    $gcloudBinPath = $null
    $commonPaths = @(
        "$env:APPDATA\..\Local\Google\Cloud SDK\google-cloud-sdk\bin",
        "$env:APPDATA\Google\Cloud SDK\google-cloud-sdk\bin",
        "C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin",
        "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin"
    )
    
    # Check if gcloud is already in PATH
    $gcloudCmd = Get-Command gcloud -ErrorAction SilentlyContinue
    if ($gcloudCmd) {
        $gcloudBinPath = Split-Path -Parent $gcloudCmd.Source
        Write-Info "Found gcloud in PATH: $gcloudBinPath"
    } else {
        # Try common installation paths
        foreach ($path in $commonPaths) {
            if (Test-Path "$path\gcloud.cmd") {
                $gcloudBinPath = $path
                Write-Info "Found gcloud at: $gcloudBinPath"
                Write-Info "Adding to PATH for this session..."
                $env:Path += ";$gcloudBinPath"
                break
            }
        }
    }
    
    if (-not $gcloudBinPath) {
        Write-Error_ "gcloud CLI not found in PATH or common locations."
        Write-Info "Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    }
    
    $gcloudVersion = & gcloud --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error_ "gcloud CLI found but failed to run: $gcloudVersion"
        exit 1
    }
    Write-Success "gcloud CLI found and working"

    # Check if authenticated
    Write-Info "Checking GCP authentication..."
    $accounts = & gcloud auth list 2>&1
    if ($accounts -match "ACTIVE  \*") {
        Write-Success "GCP account authenticated"
    } else {
        Write-Warning_ "No active GCP account detected."
        Write-Info "Run: gcloud auth application-default login"
        $response = Read-Host "Set up authentication now? (y/n)"
        if ($response -eq 'y') {
            & gcloud auth application-default login
            if ($LASTEXITCODE -ne 0) {
                Write-Error_ "Authentication failed."
                exit 1
            }
            Write-Success "Authentication successful"
        }
    }
}

# Create .env if not exists
Write-Info "Checking for .env file..."
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Info "Creating .env from template..."
        Copy-Item ".env.example" ".env"
        Write-Success ".env created (you can edit it later)"
    } else {
        Write-Warning_ ".env.example not found, skipping .env creation"
    }
} else {
    Write-Info ".env already exists, skipping"
}

# Create venv and install dependencies
if (-not $SkipVenv) {
    Write-Info "Setting up Python virtual environment..."
    
    if (-not (Test-Path ".venv")) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Error_ "Failed to create virtual environment."
            exit 1
        }
        Write-Success "Virtual environment created"
    } else {
        Write-Info "Virtual environment already exists"
    }

    Write-Info "Activating virtual environment..."
    & .\.venv\Scripts\Activate.ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Error_ "Failed to activate virtual environment."
        Write-Info "Try running: .\.venv\Scripts\Activate.ps1"
        exit 1
    }
    Write-Success "Virtual environment activated"

    Write-Info "Upgrading pip..."
    & python -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Warning_ "Failed to upgrade pip, continuing anyway..."
    } else {
        Write-Success "pip upgraded"
    }

    Write-Info "Installing Python dependencies..."
    & pip install -r requirements.txt --prefer-binary --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error_ "Failed to install dependencies."
        exit 1
    }
    Write-Success "Dependencies installed"
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Activate venv:     .\.venv\Scripts\Activate.ps1"
Write-Host "2. Refresh role data: python scripts\refresh_roles.py"
Write-Host "3. Start Streamlit:   streamlit run app\main.py"
Write-Host ""