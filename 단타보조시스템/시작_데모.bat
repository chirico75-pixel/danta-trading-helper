@echo off
cd /d "%~dp0"
title 단타 보조 시스템 - 데모

REM 파이썬 찾기
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY (
  echo.
  echo [오류] 파이썬이 설치되어 있지 않습니다.
  echo  https://www.python.org/downloads/ 에서 설치하세요.
  echo  설치 화면 맨 아래 "Add python.exe to PATH" 를 꼭 체크하세요.
  echo.
  pause
  exit /b 1
)

REM 최초 1회 패키지 설치
if not exist ".installed" (
  echo.
  echo [설치] 처음 한 번만 필요한 부품을 설치합니다. 1~2분 걸릴 수 있습니다...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [오류] 설치 실패. 인터넷 연결 확인 후 다시 실행하세요.
    pause
    exit /b 1
  )
  echo ok> .installed
)

REM 5초 뒤 브라우저 자동 열기 (포트 8800)
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 5; Start-Process 'http://localhost:8800'"

echo.
echo ============================================================
echo   단타 보조 시스템 - 데모 모드로 켜는 중...
echo   잠시 후 브라우저가 자동으로 열립니다.  주소: localhost:8800
echo   화면 왼쪽 위에 "단타 보조 시스템" 글자가 보이면 정상입니다.
echo   끄려면 이 창에서 Ctrl+C 또는 창을 닫으세요.
echo ============================================================
echo.

%PY% main.py
pause
