@echo off
chcp 65001 >nul
echo ==========================================
echo    BIMBase插件环境配置工具
echo ==========================================
echo.
echo 正在启动自动环境部署...
echo 接收到的安装目录: %1
echo.

REM 切换到脚本所在目录的上一级
cd %~dp0

echo 当前工作目录: %cd%
echo.

REM 设置Python路径
set "pyPath=%~1\PythonScript\python-3.7.9-embed-amd64\"
set "pipPath=%~1\PythonScript\python-3.7.9-embed-amd64\Scripts\"
set "getPipPath=%~1\PythonScript\python-3.7.9-embed-amd64\get-pip.py"

echo Python解释器路径: %pyPath%
echo Pip路径: %pipPath%
echo Get-pip路径: %getPipPath%
echo.

REM 检查Python是否存在
if not exist "%pyPath%python.exe" (
    echo [错误] Python解释器不存在: %pyPath%python.exe
    pause
    exit /b 1
)

echo [1/3] Python环境检查通过
echo.

REM 步骤1: 安装pip（如果尚未安装）
echo [2/3] 正在检查和安装pip...
echo.

if exist "%pipPath%pip3.exe" (
    echo pip3已存在，跳过安装
) else (
    if exist "%getPipPath%" (
        echo 正在安装pip3...
        "%pyPath%python.exe" "%getPipPath%" -i https://pypi.tuna.tsinghua.edu.cn/simple/
        if errorlevel 1 (
            echo [警告] pip安装可能出现问题，尝试继续...
        ) else (
            echo pip3安装成功
        )
    ) else (
        echo [警告] get-pip.py不存在，跳过pip安装
    )
)
echo.

REM 步骤2: 安装openpyxl
echo [3/3] 正在安装openpyxl库...
echo.

if exist "%pipPath%pip3.exe" (
    echo 使用pip3安装openpyxl...
    "%pipPath%pip3.exe" install openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple/
    if errorlevel 1 (
        echo [错误] openpyxl安装失败
        pause
        exit /b 1
    ) else (
        echo openpyxl安装成功
    )
) else (
    echo 尝试使用python -m pip安装...
    "%pyPath%python.exe" -m pip install openpyxl -i https://pypi.tuna.tsinghua.edu.cn/simple/
    if errorlevel 1 (
        echo [错误] openpyxl安装失败
        pause
        exit /b 1
    ) else (
        echo openpyxl安装成功
    )
)

echo.
echo ==========================================
echo    环境配置完成！
echo ==========================================
echo.
echo 已安装/更新的组件:
echo   - pip3 (Python包管理器)
echo   - openpyxl (Excel文件读写库)
echo.
echo 现在您可以使用XLSX格式的要素表了！
echo.

@PAUSE
