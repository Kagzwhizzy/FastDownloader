FastDownloader 1.0 - fast file + video downloader (IDM style)
==============================================================

WHAT IT DOES
- Fast downloads: splits each file into up to 32 parts downloaded at once, with pause/resume
  (even after closing the app or restarting the PC).
- Videos from YouTube and ~1800 other sites: a popup shows ONLY the qualities the video really
  has (4K, 2K, 1080p, 720p, 480p ...) with sizes, plus "Audio only (MP3)".
- Browser button: a "Download this video" button appears on top of videos in Chrome/Brave/Edge.
- Catches normal browser downloads (exe, zip, iso, pdf, mp4 ...) and downloads them faster.
- Support window: PayPal + USDT (BEP20 / ERC20).
- No server needed. Everything runs on the user's own PC.
- Note: DRM-protected streaming (Netflix, Prime, Disney+ ...) cannot be downloaded.

1) RUN THE APP
   dist\FastDownloader\FastDownloader.exe
   (Closing the window keeps it running in the tray, bottom-right, so the browser button works.
    Right-click the tray icon -> Quit to really close it.
    Settings -> "Start FastDownloader when Windows starts" keeps it always ready.)

2) ADD THE BROWSER EXTENSION (Chrome / Brave / Edge)
   a. Open  chrome://extensions  (Brave: brave://extensions, Edge: edge://extensions)
   b. Turn on "Developer mode" (top right)
   c. Click "Load unpacked" and choose the folder:  D:\FastDownloader\extension
   d. Pin the blue arrow icon. Open any video -> click "Download this video" on the video.

3) SHARE IT WITH OTHER PEOPLE
   Zip the whole folder dist\FastDownloader  plus the  extension  folder.
   Windows may say "Windows protected your PC / unknown publisher": click More info -> Run anyway.
   (Removing that warning needs a paid code-signing certificate.)
   Later the extension can be put on the Chrome Web Store ($5 one-time developer fee),
   but Google does not allow YouTube downloading there - publish it on Edge Add-ons / your own site.

CHANGE DONATION DETAILS
   fastdl\config.py  -> PAYPAL_EMAIL, USDT_ADDRESS, then run build.bat again.

KEEP YOUTUBE WORKING
   YouTube changes often. When videos stop working, update yt-dlp and rebuild:
     .venv\Scripts\python.exe -m pip install -U "yt-dlp[default]"
     build.bat

FILES
   app.py              main window + popups
   fastdl\engine.py    download engine (multi-part, resume, video)
   fastdl\video.py     quality detection (yt-dlp), ffmpeg/deno setup
   fastdl\bridge.py    local link between the browser extension and the app (127.0.0.1 only)
   extension\          browser extension
   build.bat           builds dist\FastDownloader\FastDownloader.exe
