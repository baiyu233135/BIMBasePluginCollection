@echo off
echo Starting automatic deployment of the environment...
echo Received install directory: %1
echo.
cd %~dp0
cd ..
cd ..
cd ..

set "pyPath=%~1\PythonScript\python-3.7.9-embed-amd64\"
::setlocal

:: 更改代码页到UTF-8以支持中文路径
chcp 65001

:: 获取批处理文件所在目录，并生成临时Python文件路径
set TEMP_PY_FILE=%~dp0temp_clipboard_content.py

:: 使用PowerShell命令从剪贴板读取内容，并确保换行符被正确处理后以UTF-8无BOM格式写入到临时Python文件
powershell -NoProfile -Command "$Content = Get-Clipboard -Raw; $UTF8NoBOM = New-Object System.Text.UTF8Encoding $False; [System.IO.File]::WriteAllText('%TEMP_PY_FILE%', $Content, $UTF8NoBOM)"

:: 使用指定的Python解释器运行临时Python文件
"%pyPath%\python.exe" "%TEMP_PY_FILE%"

:: 运行结束后删除临时Python文件（如不需要保留临时文件，请取消以下注释）
:: del "%TEMP_PY_FILE%"

endlocal