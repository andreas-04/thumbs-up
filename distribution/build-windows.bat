@echo off
REM Build script for creating Windows .exe installer
REM This should be run on a Windows machine with Python and PyInstaller installed

echo ==========================================
echo Building ThumbsUp Client Windows Installer
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.8 or later.
    exit /b 1
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist\thumbsup-client.exe del /q dist\thumbsup-client.exe

REM Create certs directory if it doesn't exist
if not exist certs mkdir certs

REM Build executable with PyInstaller
echo.
echo Building executable with PyInstaller...
pyinstaller thumbsup-client.spec --clean

if errorlevel 1 (
    echo Error: PyInstaller build failed
    exit /b 1
)

REM Check if NSIS is available
where makensis >nul 2>&1
if errorlevel 1 (
    echo.
    echo ==========================================
    echo Build complete!
    echo ==========================================
    echo.
    echo Executable location: dist\thumbsup-client.exe
    echo.
    echo Note: NSIS not found. Install NSIS to create installer.
    echo Download from: https://nsis.sourceforge.io/Download
    echo.
    echo After installing NSIS, run:
    echo   makensis installer.nsi
    echo.
    exit /b 0
)

REM Create LICENSE file if it doesn't exist
if not exist LICENSE (
    echo MIT License > LICENSE
    echo. >> LICENSE
    echo Copyright (c) 2025 ThumbsUp Project >> LICENSE
)

REM Build installer with NSIS
echo.
echo Building installer with NSIS...
makensis installer.nsi

if errorlevel 1 (
    echo Error: NSIS build failed
    exit /b 1
)

echo.
echo ==========================================
echo Build complete!
echo ==========================================
echo.
echo Installer location: dist\ThumbsUp-Client-Setup.exe
echo.
echo To test:
echo   1. Run dist\ThumbsUp-Client-Setup.exe as Administrator
echo   2. Follow installation wizard
echo   3. Place certificates in: C:\Program Files\ThumbsUp Client\certs\
echo   4. Open Command Prompt as Administrator
echo   5. Run: thumbsup-client
echo.
