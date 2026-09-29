#!/usr/bin/env bash
# JOGO DAS CARETAS - inicia o jogo (não precisa de internet).
#   ./start.sh               tela cheia, câmera do config.yaml
#   ./start.sh --debug       já abre com o painel de calibração
#   ./start.sh --windowed    em janela
#   ./start.sh --check       só verifica se está tudo pronto
# Se o jogo fechar por erro, ele é reaberto sozinho. Para sair de vez: Q ou Esc duas vezes.
set -u
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -x .venv/bin/python ]; then
    echo "Ambiente não encontrado. Rode ./setup.sh uma vez (com internet)."
    exit 1
fi

# Webcam do Windows -> WSL (usbipd). Se falhar, o jogo abre mesmo assim e fica tentando reconectar.
if [[ " $* " != *" --video "* ]] && [ -z "${CARETAS_SKIP_CAMERA:-}" ]; then
    ./scripts/camera_wsl.sh attach || echo "[aviso] câmera não conectada ainda; o jogo vai continuar tentando."
fi

export OPENCV_LOG_LEVEL=ERROR
restarts=0
while true; do
    .venv/bin/python -m caretas "$@"
    code=$?
    # 0 = saiu pelo teclado; 2 = erro no config.yaml (reabrir não adianta)
    if [ "$code" -eq 0 ] || [ "$code" -eq 2 ] || [[ " $* " == *" --check "* ]]; then
        exit "$code"
    fi
    restarts=$((restarts + 1))
    if [ "$restarts" -gt 20 ]; then
        echo "[erro] o jogo fechou $restarts vezes seguidas; veja as mensagens acima."
        exit "$code"
    fi
    echo "[aviso] o jogo fechou inesperadamente (código $code). Reabrindo em 3 s... (Ctrl+C cancela)"
    sleep 3
done
