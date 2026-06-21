@echo off
REM ============================================================================
REM  MiniCrew — double-click launcher for Windows.
REM  Opens the MiniCrew literature UI as a chrome-less "app window" (Edge).
REM
REM  Prereq: the Streamlit backend runs on the Linux node and its port is
REM  forwarded to this PC at localhost:8501.
REM    - On the node:        scripts/minicrew-app
REM    - Forwarding: VS Code Remote-SSH does it automatically; or open an SSH
REM      tunnel:  ssh -L 8501:localhost:8501 <user>@<node>
REM
REM  To change the port, edit URL below.
REM ============================================================================
title MiniCrew Literature
set "URL=http://localhost:8501"

REM --- is the backend reachable? (Windows 10+ ships curl) ---
curl -s -o nul -m 3 "%URL%/_stcore/health"
if errorlevel 1 (
  echo.
  echo   MiniCrew is not reachable at %URL%
  echo.
  echo   Start it on the server first:   scripts/minicrew-app
  echo   and make sure the port is forwarded to this PC.
  echo   ^(VS Code Remote-SSH forwards it automatically;
  echo    or run:  ssh -L 8501:localhost:8501 USER@NODE^)
  echo.
  pause
  exit /b 1
)

REM --- open as an app window (Edge is built into Windows 10/11) ---
start "" msedge --app="%URL%"
if errorlevel 1 start "" chrome --app="%URL%"
if errorlevel 1 start "" "%URL%"
exit /b 0
