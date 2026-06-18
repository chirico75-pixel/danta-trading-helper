@echo off
cd /d "%~dp0"
title 단타 보조 시스템 - 테스트 검증

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY (
  echo [오류] 파이썬이 없습니다. 먼저 시작_데모.bat 를 한 번 실행하세요.
  pause
  exit /b 1
)

echo ============================================================
echo   자동 테스트를 실행합니다 (코드가 정상인지 확인)
echo ============================================================
echo.
%PY% -m pytest tests/ -v

echo.
echo ============================================================
echo   위 결과 맨 아래에  "12 passed" 가 보이면 정상입니다.
echo ============================================================
echo.
pause
