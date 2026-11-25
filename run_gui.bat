@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "SCRIPT=java2bbmodel_gui.py"

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%SCRIPT%"
    exit /b
)
where py >nul 2>nul
if %errorlevel%==0 (
    start "" py -3 "%SCRIPT%"
    exit /b
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%~fD\pythonw.exe" (
        start "" "%%~fD\pythonw.exe" "%SCRIPT%"
        exit /b
    )
)
for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%~fD\pythonw.exe" (
        start "" "%%~fD\pythonw.exe" "%SCRIPT%"
        exit /b
    )
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%SCRIPT%"
    exit /b
)
echo 没找到可用的 Python 3。
echo 请到 https://www.python.org/downloads/ 安装，安装时勾选 "Add python.exe to PATH"。
pause
