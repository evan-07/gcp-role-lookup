#!/usr/bin/env bash

# GCP IAM Lookup - Linux/macOS Setup Helper
#
# Purpose: Validate prerequisites and optionally set up ADC on Linux/macOS.
# Usage: ./setup_linux.sh
#
# This script will:
# 1. Check for Python 3.12+
# 2. Optionally check for gcloud CLI
# 3. Optionally run gcloud auth application-default login
# 4. Create virtual environment and install dependencies
# 5. Start Streamlit automatically

set -euo pipefail

SKIP_GCLOUD=false
SKIP_VENV=false

for arg in "$@"; do
  case "$arg" in
    --skip-gcloud) SKIP_GCLOUD=true ;;
    --skip-venv) SKIP_VENV=true ;;
    *)
      echo "[ERROR] Unknown option: $arg"
      echo "Usage: ./setup_linux.sh [--skip-gcloud] [--skip-venv]"
      exit 1
      ;;
  esac
done

info() { echo -e "\033[1;36m[INFO]\033[0m $*"; }
success() { echo -e "\033[1;32m[OK]\033[0m $*"; }
warning() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

echo
echo "=== GCP IAM Lookup - Linux/macOS Setup Helper ==="
echo

SETUP_ADC_NOW=false
if [ "$SKIP_GCLOUD" = false ]; then
  info "ADC login is optional - only needed if you want to refresh role data from the GCP API."
  info "The app works offline with the bundled data files."
  read -r -p "Configure ADC now? (y/N) " adc_response
  if [[ "$adc_response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    SETUP_ADC_NOW=true
  else
    SKIP_GCLOUD=true
    info "Skipping gcloud / ADC setup. Run 'gcloud auth application-default login' later if needed."
  fi
fi

info "Checking Python 3.12+..."
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  error "Python not found in PATH."
  exit 1
fi

PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_MAJOR="${PYTHON_VERSION%%.*}"
PYTHON_MINOR="${PYTHON_VERSION##*.}"

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]; }; then
  error "Python ${PYTHON_VERSION} found, but 3.12+ required."
  exit 1
fi
success "Python ${PYTHON_VERSION} found"

if [ "$SKIP_GCLOUD" = false ]; then
  info "Checking gcloud CLI..."
  if ! command -v gcloud >/dev/null 2>&1; then
    error "gcloud CLI not found in PATH."
    info "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
  success "gcloud CLI found"

  if [ "$SETUP_ADC_NOW" = true ]; then
    info "Starting optional ADC login..."
    gcloud auth application-default login
    success "ADC authentication successful"
  else
    info "Skipping ADC login (optional)."
    info "You can run later: gcloud auth application-default login"
  fi
fi

if [ "$SKIP_VENV" = false ]; then
  info "Setting up Python virtual environment..."
  if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
    success "Virtual environment created"
  else
    info "Virtual environment already exists"
  fi

  info "Activating virtual environment..."
  # shellcheck disable=SC1091
  source .venv/bin/activate
  success "Virtual environment activated"

  info "Upgrading pip..."
  python -m pip install --upgrade pip >/dev/null 2>&1 || warning "Failed to upgrade pip, continuing..."

  info "Installing Python dependencies..."
  pip install -r requirements.txt --prefer-binary
  pip install -e . --no-deps
  success "Package installed in editable mode"
  success "Dependencies installed"
else
  info "Skipping virtual environment setup (--skip-venv)."
fi

echo
echo "=== Setup Complete ==="
info "Starting Streamlit on http://localhost:8501 ..."
exec streamlit run app/main.py
