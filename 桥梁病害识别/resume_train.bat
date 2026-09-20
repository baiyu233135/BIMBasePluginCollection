@echo off
set RESUME=1
cd /d %~dp0
"C:\temp\ul_80145\Scripts\python.exe" "training\train_v2.py" >> "train_v2_resume.log" 2>&1
