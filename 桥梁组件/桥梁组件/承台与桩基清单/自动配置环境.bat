@echo off
echo Starting automatic deployment of the environment...
echo Received install directory: %1
echo.
cd %~dp0
cd ..
cd ..
cd ..

set "pyPath=%~1\PythonScript\python-3.7.9-embed-amd64\"
set "pipPath=%~1\PythonScript\python-3.7.9-embed-amd64\Scripts\"
echo Python interpreter path: %pyPath%
echo.
echo Pip3 path: %pipPath%

echo.
echo Pip3 installing
echo.
"%pyPath%\python.exe" "%pyPath%\get-pip.py" -i https://pypi.tuna.tsinghua.edu.cn/simple/

echo.
echo openpyxl installing
echo.
"%pipPath%\pip3.exe" install openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple/

echo.
echo pymeshlab installing (system Python, for FBX to STL conversion)
echo.
python -m pip install pymeshlab -i https://pypi.tuna.tsinghua.edu.cn/simple/
if errorlevel 1 (
    echo Failed with 'python', trying 'python3'...
    python3 -m pip install pymeshlab -i https://pypi.tuna.tsinghua.edu.cn/simple/
)
if errorlevel 1 (
    echo WARNING: Could not install pymeshlab automatically.
    echo Please manually run: pip install pymeshlab
)

@PAUSE