@echo off
setlocal enabledelayedexpansion

:: Highlight Processor — convenience wrapper for Docker Compose commands

if "%~1"=="" goto :help
if "%~1"=="help" goto :help
if "%~1"=="--help" goto :help
if "%~1"=="-h" goto :help

if "%~1"=="process" goto :process
if "%~1"=="process-all" goto :process_all
if "%~1"=="upload" goto :upload
if "%~1"=="upload-ig" goto :upload_ig
if "%~1"=="upload-yt" goto :upload_yt
if "%~1"=="upload-tt" goto :upload_tt
if "%~1"=="crop" goto :crop
if "%~1"=="scrub" goto :scrub
if "%~1"=="normalize" goto :normalize
if "%~1"=="auth-yt" goto :auth_yt
if "%~1"=="auth-tt" goto :auth_tt
if "%~1"=="tunnel" goto :tunnel
if "%~1"=="list" goto :list
if "%~1"=="build" goto :build

echo Unknown command: %~1
echo.
goto :help

:: ————————————————————————————————————————————————————————————
:help
echo.
echo   Highlight Processor
echo   ====================
echo.
echo   PROCESS
echo     run process ^<file^>        Crop, scrub vocals, normalize, and upload
echo     run process-all            Process + upload all unprocessed videos
echo.
echo   UPLOAD (already-processed _final videos)
echo     run upload ^<file^>         Upload to Instagram + YouTube + TikTok
echo     run upload-ig ^<file^>      Upload to Instagram Reels only
echo     run upload-yt ^<file^>      Upload to YouTube Shorts only
echo     run upload-tt ^<file^>      Upload to TikTok only
echo.
echo   INDIVIDUAL STEPS
echo     run crop ^<file^>           Crop video to 9:16 (1080x1920)
echo     run scrub ^<file^>          Remove vocals from audio
echo     run normalize ^<file^>      Normalize audio loudness
echo.
echo   AUTH
echo     run auth-yt                YouTube OAuth flow (opens browser)
echo     run auth-tt                TikTok OAuth flow (opens browser)
echo.
echo   OTHER
echo     run tunnel                 Start ngrok + file server (background)
echo     run list                   List videos in the videos/ folder
echo     run build                  Rebuild Docker images
echo.
echo   ^<file^> is a path inside the container, e.g. "/videos/myclip.mp4"
echo.
goto :eof

:: ————————————————————————————————————————————————————————————
:process
if "%~2"=="" (
    echo Usage: run process ^<file^>
    echo   e.g. run process "/videos/myclip.mp4"
    exit /b 1
)
docker compose run --rm process "%~2"
goto :eof

:process_all
docker compose run --rm process_all /videos
goto :eof

:upload
if "%~2"=="" (
    echo Usage: run upload ^<file^>
    echo   e.g. run upload "/videos/clip_final.mp4"
    exit /b 1
)
docker compose run --rm upload_one_video "%~2"
goto :eof

:upload_ig
if "%~2"=="" (
    echo Usage: run upload-ig ^<file^>
    exit /b 1
)
docker compose run --rm instagram_upload "%~2"
goto :eof

:upload_yt
if "%~2"=="" (
    echo Usage: run upload-yt ^<file^>
    exit /b 1
)
docker compose run --rm youtube_upload "%~2"
goto :eof

:upload_tt
if "%~2"=="" (
    echo Usage: run upload-tt ^<file^>
    exit /b 1
)
docker compose run --rm tiktok_upload "%~2"
goto :eof

:crop
if "%~2"=="" (
    echo Usage: run crop ^<file^>
    exit /b 1
)
docker compose run --rm crop "%~2"
goto :eof

:scrub
if "%~2"=="" (
    echo Usage: run scrub ^<file^>
    exit /b 1
)
docker compose run --rm scrub_voices "%~2"
goto :eof

:normalize
if "%~2"=="" (
    echo Usage: run normalize ^<file^>
    exit /b 1
)
docker compose run --rm normalize "%~2"
goto :eof

:auth_yt
docker compose run --rm -p 8080:8080 youtube_upload --auth
goto :eof

:auth_tt
docker compose run --rm -p 8080:8080 tiktok_upload --auth
goto :eof

:tunnel
docker compose up -d ngrok
echo ngrok tunnel started. Dashboard: http://localhost:4040
goto :eof

:list
dir /b videos\*.mp4 2>nul
if errorlevel 1 echo No .mp4 files found in videos/
goto :eof

:build
docker compose build
goto :eof
