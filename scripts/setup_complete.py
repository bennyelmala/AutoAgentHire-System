#!/usr/bin/env python3
"""
AutoAgentHire - Complete Installation & Setup Script
Checks dependencies, configures environment, and validates setup
"""
import sys
import subprocess
import os
from pathlib import Path
import shutil


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Print success message."""
    print(f"✓ {text}")


def print_error(text):
    """Print error message."""
    print(f"✗ {text}")


def print_warning(text):
    """Print warning message."""
    print(f"⚠ {text}")


def check_python_version():
    """Check if Python version is 3.11+."""
    print_header("Checking Python Version")
    
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro} detected")
    
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_error("Python 3.11 or higher is required")
        print("Please install Python 3.11+ from https://www.python.org/downloads/")
        return False
    
    print_success("Python version is compatible")
    return True


def check_pip():
    """Check if pip is available."""
    print_header("Checking pip")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout.strip())
        print_success("pip is available")
        return True
    except subprocess.CalledProcessError:
        print_error("pip is not available")
        return False


def create_virtual_environment():
    """Create virtual environment."""
    print_header("Setting Up Virtual Environment")
    
    venv_path = Path("venv")
    
    if venv_path.exists():
        print_warning("Virtual environment already exists")
        response = input("Recreate it? (y/N): ").lower()
        if response == 'y':
            shutil.rmtree(venv_path)
        else:
            print_success("Using existing virtual environment")
            return True
    
    try:
        print("Creating virtual environment...")
        subprocess.run(
            [sys.executable, "-m", "venv", "venv"],
            check=True
        )
        print_success("Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to create virtual environment")
        return False


def get_venv_python():
    """Get path to Python in virtual environment."""
    if sys.platform == "win32":
        return Path("venv/Scripts/python.exe")
    else:
        return Path("venv/bin/python")


def install_dependencies():
    """Install Python dependencies."""
    print_header("Installing Dependencies")
    
    venv_python = get_venv_python()
    
    if not venv_python.exists():
        print_error("Virtual environment Python not found")
        return False
    
    # Upgrade pip first
    print("Upgrading pip...")
    try:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            check=True
        )
    except subprocess.CalledProcessError:
        print_warning("Could not upgrade pip")
    
    # Install requirements
    print("Installing requirements (this may take several minutes)...")
    try:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        print_success("Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies")
        return False


def install_playwright():
    """Install Playwright browsers."""
    print_header("Installing Playwright Browsers")
    
    venv_python = get_venv_python()
    
    print("Installing Chromium browser...")
    try:
        subprocess.run(
            [str(venv_python), "-m", "playwright", "install", "chromium"],
            check=True
        )
        print_success("Playwright browsers installed")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install Playwright browsers")
        return False


def create_directories():
    """Create necessary directories."""
    print_header("Creating Directories")
    
    directories = [
        "uploads/resumes",
        "uploads/cover_letters",
        "logs",
        "vector_store",
        "data/job_listings",
        "data/logs",
        "data/resumes",
        "data/templates"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created: {directory}")
    
    print_success("All directories created")
    return True


def setup_env_file():
    """Setup .env file."""
    print_header("Configuring Environment")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print_warning(".env file already exists")
        response = input("Overwrite with template? (y/N): ").lower()
        if response != 'y':
            print_success("Keeping existing .env file")
            return True
    
    if not env_example.exists():
        print_error(".env.example not found")
        return False
    
    shutil.copy(env_example, env_file)
    print_success(".env file created from template")
    
    print("\n⚠️  IMPORTANT: You need to edit .env and add your API keys:")
    print("   - GOOGLE_API_KEY (required)")
    print("   - OPENAI_API_KEY (optional)")
    print("   - Other configurations as needed")
    print("\nEdit .env now? (y/N): ", end="")
    
    response = input().lower()
    if response == 'y':
        if sys.platform == "win32":
            os.system(f"notepad {env_file}")
        elif sys.platform == "darwin":
            os.system(f"open -e {env_file}")
        else:
            os.system(f"nano {env_file}")
    
    return True


def validate_env():
    """Validate environment variables."""
    print_header("Validating Configuration")
    
    env_file = Path(".env")
    
    if not env_file.exists():
        print_error(".env file not found")
        return False
    
    required_vars = ["GOOGLE_API_KEY", "SECRET_KEY"]
    missing = []
    
    with open(env_file) as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" not in content or f"{var}=\"\"" in content or f"{var}=your-" in content:
                missing.append(var)
    
    if missing:
        print_warning(f"Missing or invalid configuration: {', '.join(missing)}")
        print("Please edit .env and add these values")
        return False
    
    print_success("Configuration is valid")
    return True


def test_backend():
    """Test if backend can start."""
    print_header("Testing Backend")
    
    venv_python = get_venv_python()
    
    print("Attempting to import backend modules...")
    try:
        result = subprocess.run(
            [str(venv_python), "-c", "from backend.main import app; print('OK')"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "OK" in result.stdout:
            print_success("Backend imports successfully")
            return True
        else:
            print_error("Backend import failed")
            if result.stderr:
                print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Backend import timed out")
        return False
    except Exception as e:
        print_error(f"Backend test failed: {e}")
        return False


def print_next_steps():
    """Print next steps for user."""
    print_header("Setup Complete! 🎉")
    
    print("\nNext Steps:")
    print("\n1. Make sure you've configured .env with your API keys:")
    print("   - GOOGLE_API_KEY (Get from: https://makersuite.google.com/app/apikey)")
    print("   - Other optional keys")
    
    print("\n2. Start the application:")
    if sys.platform == "win32":
        print("   .\\startup.bat")
    else:
        print("   ./startup.sh")
    
    print("\n3. Or start services manually:")
    print("   Terminal 1: uvicorn backend.main:app --reload")
    print("   Terminal 2: streamlit run frontend/streamlit/app_enhanced.py")
    
    print("\n4. Open your browser:")
    print("   Frontend: http://localhost:8501")
    print("   API Docs: http://localhost:8000/docs")
    
    print("\n5. Read the documentation:")
    print("   COMPLETE_USER_GUIDE.md")
    
    print("\nNeed help? Check:")
    print("   - GitHub Issues: https://github.com/yourusername/LinkedIn-Job-Automation-with-AI")
    print("   - Documentation: README.md")
    
    print("\n" + "=" * 60)


def main():
    """Main setup function."""
    print("\n" + "🤖" * 30)
    print("  AutoAgentHire - Setup & Installation")
    print("🤖" * 30)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check pip
    if not check_pip():
        sys.exit(1)
    
    # Create virtual environment
    if not create_virtual_environment():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Install Playwright
    if not install_playwright():
        print_warning("Playwright installation failed, but continuing...")
    
    # Create directories
    if not create_directories():
        sys.exit(1)
    
    # Setup .env
    if not setup_env_file():
        sys.exit(1)
    
    # Validate environment (may fail if user hasn't configured yet)
    if not validate_env():
        print_warning("Environment validation failed. Please configure .env before running.")
    
    # Test backend
    if not test_backend():
        print_warning("Backend test failed. Check logs when running.")
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
