@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "java2bbmodel_gui.py"
    exit /b
)
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "java2bbmodel_gui.py"
    exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
    start "" python "java2bbmodel_gui.py"
    exit /b
)
echo 没找到 Python。请先安装 Python 3.8+，安装时勾选 "Add python.exe to PATH"。
pause
