@echo off
setlocal
cd /d "%~dp0"

REM 一键启动 MySQL、MCP、Agent 和 Streamlit，并自动打开浏览器。
if exist "D:\Anaconda\envs\lang_env\python.exe" (
  "D:\Anaconda\envs\lang_env\python.exe" start_demo.py
) else (
  python start_demo.py
)

pause
