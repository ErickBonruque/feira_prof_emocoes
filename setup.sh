#!/usr/bin/env bash
# JOGO DAS CARETAS - preparação (a ÚNICA etapa que precisa de internet).
# Cria o ambiente Python, instala as dependências fixadas, baixa modelos e fontes,
# cria o atalho do Windows e roda os testes. Pode rodar de novo quantas vezes quiser.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ROOT=$(pwd)

echo "== 1/5 Ambiente Python (.venv)"
if [ ! -x .venv/bin/python ]; then
    if ! python3 -c "import ensurepip" 2>/dev/null; then
        echo "   instalando python3-venv (pede a senha do sudo)"
        sudo apt-get install -y python3-venv
    fi
    python3 -m venv .venv
fi
.venv/bin/python --version

echo "== 2/5 Dependências (versões fixadas em requirements.txt)"
.venv/bin/pip install --upgrade --quiet pip
.venv/bin/pip install --timeout 60 --retries 10 -r requirements-dev.txt

echo "== 3/5 Modelos e fontes (com conferência de SHA-256)"
.venv/bin/python scripts/download_assets.py

echo "== 4/5 Atalho para o Windows (start.bat)"
DISTRO="${WSL_DISTRO_NAME:-Ubuntu}"
cat > start.bat <<EOF
@echo off
rem JOGO DAS CARETAS - duplo clique para iniciar (gerado pelo setup.sh)
title Jogo das Caretas
wsl.exe -d $DISTRO --cd $ROOT --exec bash ./start.sh %*
if errorlevel 1 (
  echo.
  echo O jogo fechou com erro. Veja as mensagens acima.
  pause
)
EOF
sed -i 's/$/\r/' start.bat
if command -v powershell.exe > /dev/null; then
    DESKTOP=$(cd /mnt/c && powershell.exe -NoProfile -Command \
        '[Console]::OutputEncoding=[Text.Encoding]::UTF8; [Environment]::GetFolderPath("Desktop")' | tr -d '\r')
    if [ -n "$DESKTOP" ]; then
        WIN_DESKTOP=$(wslpath "$DESKTOP")
        cp start.bat "$WIN_DESKTOP/Jogo das Caretas.bat" && echo "   atalho criado em: $DESKTOP\\Jogo das Caretas.bat"
    fi
fi

echo "== 5/5 Testes e verificação"
.venv/bin/python -m pytest -q
.venv/bin/python -m caretas --check || true

echo
echo "Setup concluído. Se a câmera ainda não foi configurada no WSL (uma vez só):"
echo "   ./scripts/camera_wsl.sh setup && ./scripts/camera_wsl.sh bind"
echo "Para jogar: ./start.sh   (ou duplo clique em 'Jogo das Caretas' na Área de Trabalho)"
