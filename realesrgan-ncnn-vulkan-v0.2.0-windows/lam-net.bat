@echo off
chcp 65001 >nul
setlocal

REM ============================================================
REM  Lam net anh truyen scan bang Real-ESRGAN (ncnn / Vulkan)
REM  - Tu neo duong dan theo vi tri file .bat (%~dp0)
REM  - Input : input\            (bo anh nguon vao day)
REM  - Output: output-realesrgan\ (anh da lam net ra day)
REM  - Model : realesr-animevideov3  |  Scale: 2x  (da chot sau khi test)
REM  - Format: webp (lossless, nhe hon png)
REM  - Tile  : co dinh 200 (an toan VRAM 4GB, khong giam chat luong)
REM ============================================================

cd /d "%~dp0"

set "EXE=%~dp0realesrgan-ncnn-vulkan.exe"
set "MODEL=realesr-animevideov3"
set "SCALE=2"
set "FORMAT=webp"
set "TILE=200"
set "IN=input"
set "OUT=output-realesrgan"

if not exist "%IN%"  mkdir "%IN%"
if not exist "%OUT%" mkdir "%OUT%"

echo ============================================================
echo   Real-ESRGAN - Lam net anh truyen
echo   Model : %MODEL%   ^|   Scale: %SCALE%x   ^|   Format: %FORMAT%   ^|   Tile: %TILE%
echo   Input : %IN%\
echo   Output: %OUT%\
echo ============================================================
echo.

set "ANYERR=0"

REM --- 1) Anh nam TRUC TIEP trong input\ (khong nam trong folder con) ---
echo --- Xu ly anh phang trong %IN%\ ---
"%EXE%" -i "%IN%" -o "%OUT%" -n %MODEL% -s %SCALE% -f %FORMAT% -t %TILE%
if errorlevel 1 set "ANYERR=1"

REM --- 2) Moi FOLDER CON (vd chapter 1, 2, 3...) -> giu nguyen cau truc ra output ---
for /d %%D in ("%IN%\*") do (
  echo.
  echo --- Xu ly folder: %%~nxD ---
  if not exist "%OUT%\%%~nxD" mkdir "%OUT%\%%~nxD"
  "%EXE%" -i "%%D" -o "%OUT%\%%~nxD" -n %MODEL% -s %SCALE% -f %FORMAT% -t %TILE%
  if errorlevel 1 set "ANYERR=1"
)

echo.
if "%ANYERR%"=="1" (
  echo [LOI] Co it nhat 1 anh/folder loi. Xem log ben tren.
) else (
  echo [XONG] Da lam net xong. Ket qua trong thu muc: %OUT%\
)
echo.
pause
endlocal
