@echo off
REM Builds dist\FastDownloader\FastDownloader.exe (folder version = starts fast, fewer antivirus false alarms)
cd /d "%~dp0"
.venv\Scripts\python.exe make_icons.py
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --onedir --name FastDownloader ^
  --icon assets\app.ico --add-data "assets;assets" ^
  --collect-data imageio_ffmpeg --collect-all yt_dlp --collect-all yt_dlp_ejs ^
  --add-binary ".venv\Scripts\deno.exe;deno" ^
  app.py
echo.
echo Done: dist\FastDownloader\FastDownloader.exe
