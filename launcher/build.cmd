@echo off
rem Builds mevr-launcher.exe (the Mirror's Edge WXR launcher).
rem Needs an x86 MSVC toolchain only: no DirectX SDK, no OpenXR, no MinHook.
setlocal
cd /d "%~dp0"

if not defined VCINSTALLDIR call :findvc
if not defined VS (echo [FAIL] no Visual Studio with C++ tools found. & exit /b 1)
call "%VS%\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 (echo [FAIL] vcvarsall x86 failed. & exit /b 1)

where cl.exe >nul 2>&1
if errorlevel 1 (echo [FAIL] cl.exe not found - run from an x86 Developer prompt. & exit /b 1)

cl.exe /nologo /O2 /MT /EHsc /W3 /DUNICODE /D_UNICODE /D_CRT_SECURE_NO_WARNINGS /c mevr-launcher.cpp
if errorlevel 1 (echo [FAIL] compile failed. & exit /b 1)

link.exe /nologo /SUBSYSTEM:WINDOWS /OUT:mevr-launcher.exe mevr-launcher.obj ^
    user32.lib shell32.lib advapi32.lib
if errorlevel 1 (echo [FAIL] link failed. & exit /b 1)

echo Built %~dp0mevr-launcher.exe
exit /b 0

:findvc
set "VS="
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
    "%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath > "%TEMP%\mevr_vs.txt" 2>nul
    set /p VS=<"%TEMP%\mevr_vs.txt"
    del "%TEMP%\mevr_vs.txt" >nul 2>&1
)
if defined VS if not exist "%VS%\VC\Auxiliary\Build\vcvarsall.bat" set "VS="
if not defined VS if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" set "VS=%ProgramFiles%\Microsoft Visual Studio\2022\Community"
if not defined VS if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat" set "VS=%ProgramFiles%\Microsoft Visual Studio\2022\Professional"
if not defined VS if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" set "VS=%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise"
if not defined VS if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" set "VS=%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools"
if not defined VS if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" set "VS=%ProgramFiles(x86)%\Microsoft Visual Studio\18\BuildTools"
exit /b 0
