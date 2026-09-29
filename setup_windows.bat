@echo off
rem JOGO DAS CARETAS (Windows nativo) - preparacao: a UNICA etapa que precisa de internet.
rem Cria o .venv com Python 3.12, instala as dependencias fixadas, baixa modelos e fontes,
rem cria o atalho na Area de Trabalho e roda os testes. Pode rodar de novo quantas vezes quiser.
rem (O caminho do WSL continua sendo setup.sh / start.sh; os dois podem conviver.)
setlocal EnableDelayedExpansion
chcp 65001 > nul
cd /d "%~dp0"
title Jogo das Caretas - setup

echo == 1/5 Ambiente Python (.venv)
if exist ".venv\Scripts\python.exe" goto :have_venv
set "PY="
rem Procura um Python 3.12: lançador py, Miniconda/Anaconda, instalação do python.org
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
for %%P in ("%USERPROFILE%\miniconda3\python.exe" "%USERPROFILE%\anaconda3\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe") do (
    if not defined PY if exist %%P (
        %%P -c "import sys;sys.exit(0 if sys.version_info[:2]==(3,12) else 1)" && set "PY=%%~P"
    )
)
if not defined PY (
    echo [erro] Python 3.12 não encontrado. Instale com: winget install Python.Python.3.12
    goto :failed
)
echo    usando !PY!
"!PY!" -m venv .venv || goto :failed
:have_venv
".venv\Scripts\python.exe" --version

echo == 2/5 Dependências (versões fixadas em requirements.txt; ~1,5 GB, a maior parte CUDA)
rem PIP_CONFIG_FILE=nul: ignora os pip.ini da máquina (um índice extra fora do ar travava a
rem instalação); tudo vem do PyPI, que é de onde as versões fixadas foram testadas.
rem Tem de ser "nul" minúsculo: o pip compara com os.devnull.
set "PIP_CONFIG_FILE=nul"
".venv\Scripts\python.exe" -m pip install --upgrade --quiet pip
".venv\Scripts\python.exe" -m pip install --timeout 60 --retries 10 -r requirements-dev.txt || goto :failed

echo == 3/5 Modelos e fontes (com conferência de SHA-256)
".venv\Scripts\python.exe" scripts\download_assets.py || goto :failed

echo == 4/5 Atalho na Área de Trabalho
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Jogo das Caretas (Windows).lnk'));" ^
  "$s.TargetPath='%~dp0start_windows.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,138'; $s.Save();" ^
  "Write-Output ('   atalho criado em: ' + (Join-Path $d 'Jogo das Caretas (Windows).lnk'))"

echo == 5/5 Testes e verificação
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" -m pytest -q || goto :failed
".venv\Scripts\python.exe" -m caretas --check

echo.
echo Setup concluído. Para jogar: duplo clique em "Jogo das Caretas (Windows)" na Área de Trabalho
echo (ou start_windows.bat nesta pasta). Conecte a webcam antes de abrir.
echo Se a câmera não for encontrada: start_windows.bat --list-cameras (ver README, "Webcam").
pause
exit /b 0

:failed
echo.
echo [erro] O setup parou. Veja as mensagens acima (internet ligada?) e rode de novo.
pause
exit /b 1
