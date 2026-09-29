@echo off
rem JOGO DAS CARETAS (Windows nativo) - duplo clique para iniciar. Nao precisa de internet.
rem   start_windows.bat               tela cheia, camera do config.yaml (C920 ou WEMISS)
rem   start_windows.bat --debug       ja abre com o painel de calibracao
rem   start_windows.bat --windowed    em janela
rem   start_windows.bat --check       so verifica se esta tudo pronto
rem Se o jogo fechar por erro, ele e reaberto sozinho. Para sair de vez: Q ou Esc duas vezes.
setlocal EnableDelayedExpansion
chcp 65001 > nul
cd /d "%~dp0"
title Jogo das Caretas

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente não encontrado. Rode setup_windows.bat uma vez ^(com internet^).
    pause
    exit /b 1
)

set "OPENCV_LOG_LEVEL=ERROR"
set "PYTHONUTF8=1"

rem --check e --list-cameras rodam uma vez só
echo(%* | findstr /i /c:"--check" /c:"--list-cameras" > nul
if not errorlevel 1 (
    ".venv\Scripts\python.exe" -m caretas %*
    set "code=!errorlevel!"
    pause
    exit /b !code!
)

set restarts=0
:loop
".venv\Scripts\python.exe" -m caretas %*
set "code=!errorlevel!"
rem 0 = saiu pelo teclado; 2 = erro no config.yaml (reabrir não adianta)
if "!code!"=="0" exit /b 0
if "!code!"=="2" goto :failed
set /a restarts+=1
if !restarts! gtr 20 (
    echo [erro] o jogo fechou !restarts! vezes seguidas; veja as mensagens acima.
    goto :failed
)
echo [aviso] o jogo fechou inesperadamente ^(código !code!^). Reabrindo em 3 s... ^(Ctrl+C cancela^)
timeout /t 3 /nobreak > nul
goto :loop

:failed
echo.
echo O jogo fechou com erro. Veja as mensagens acima.
pause
exit /b !code!
