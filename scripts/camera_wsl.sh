#!/usr/bin/env bash
# Repassa a webcam do Windows para o WSL usando o usbipd-win.
#
#   ./scripts/camera_wsl.sh setup    preparação ÚNICA do lado Linux (driver, permissão)   [pede sudo]
#   ./scripts/camera_wsl.sh bind     compartilha a câmera no Windows, UMA VEZ              [pede Administrador]
#                            (use "bind --force" se o attach disser "Device busy")
#   ./scripts/camera_wsl.sh attach   conecta a câmera ao WSL e fica reconectando sozinho (usado pelo start.sh)
#   ./scripts/camera_wsl.sh detach   desconecta do WSL (continua compartilhada)
#   ./scripts/camera_wsl.sh unbind   devolve a câmera de vez para o Windows                [pede Administrador]
#   ./scripts/camera_wsl.sh status   mostra a situação atual
#
# A câmera é escolhida pelo VID:PID de camera.usb_hardware_id no config.yaml
# (descubra com "usbipd list" no Windows). Aceita várias separadas por vírgula: usa a primeira conectada.
set -u
cd "$(dirname "$(readlink -f "$0")")/.."

# Uma ou mais câmeras (VID:PID separados por vírgula), em ordem de preferência; pick_camera escolhe.
HWIDS=$(sed -nE 's/^[[:space:]]*usb_hardware_id:(.*)/\1/p' config.yaml | head -1 | sed 's/#.*//' \
    | grep -oE "[0-9a-fA-F]{4}:[0-9a-fA-F]{4}" | tr '\n' ' ')
HWID=${HWIDS%% *}
PIDFILE="/tmp/caretas-usbipd-autoattach.pid"

USBIPD=$(command -v usbipd.exe || true)
[ -z "$USBIPD" ] && [ -x "/mnt/c/Program Files/usbipd-win/usbipd.exe" ] && USBIPD="/mnt/c/Program Files/usbipd-win/usbipd.exe"

say() { echo "[câmera] $*"; }

need_usbipd() {
    if [ -z "$USBIPD" ]; then
        say "usbipd-win não encontrado no Windows. Instale com (PowerShell): winget install usbipd"
        exit 1
    fi
    if [ -z "$HWID" ]; then
        say "camera.usb_hardware_id não definido no config.yaml"
        exit 1
    fi
}

usb_list() {
    (cd /mnt/c 2>/dev/null; "$USBIPD" list 2>/dev/null) | tr -d '\r' | sed -n '/^Connected:/,/^$/p'
}

state() {  # Not shared | Shared | Attached | (vazio = câmera não conectada ao PC)
    usb_list | grep -i " $HWID " | sed -E 's/.*  +([A-Za-z][A-Za-z ()]+)$/\1/' | head -1
}

pick_camera() {
    # Usa a primeira câmera do config que estiver conectada. Se nenhuma estiver, usa a única
    # webcam encontrada (ex.: câmera externa de outro modelo).
    local id found
    for id in $HWIDS; do
        HWID=$id
        if [ -n "$(state)" ]; then return; fi
    done
    HWID=${HWIDS%% *}
    found=$(usb_list | grep -iE "cam|webcam|video|c[0-9]{3}" | grep -oE "[0-9a-fA-F]{4}:[0-9a-fA-F]{4}" | sort -u)
    if [ "$(echo "$found" | grep -c .)" = "1" ]; then
        say "câmera $HWID do config não encontrada; usando a webcam conectada $found"
        say "(para fixar, troque camera.usb_hardware_id no config.yaml)"
        HWID="$found"
    fi
}

has_video() { compgen -G "/dev/video*" > /dev/null; }

wait_video() {
    for _ in $(seq 1 "${1:-20}"); do
        has_video && return 0
        sleep 0.5
    done
    return 1
}

autoattach_running() {
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

case "${1:-status}" in
    status)
        need_usbipd
        pick_camera
        say "câmera $HWID no Windows: $(state || true)"
        if has_video; then say "no WSL: $(ls /dev/video* | tr '\n' ' ')"; else say "no WSL: nenhum /dev/video*"; fi
        autoattach_running && say "reconexão automática: ativa (pid $(cat "$PIDFILE"))" || say "reconexão automática: parada"
        lsmod | grep -q uvcvideo && say "driver uvcvideo: carregado" || say "driver uvcvideo: NÃO carregado"
        ;;

    setup)
        set -e
        trap 'say "FALHOU (linha $LINENO). Nada foi concluído depois deste ponto."' ERR
        TARGET_USER="${SUDO_USER:-$USER}"
        SUDO=""
        [ "$(id -u)" -ne 0 ] && SUDO="sudo"
        say "instalando utilitários e preparando driver/permissões para '$TARGET_USER' (pode pedir a senha do sudo)"
        $SUDO apt-get install -y v4l-utils
        echo uvcvideo | $SUDO tee /etc/modules-load.d/caretas-uvcvideo.conf > /dev/null
        $SUDO modprobe uvcvideo
        echo 'SUBSYSTEM=="video4linux", GROUP="video", MODE="0666"' | $SUDO tee /etc/udev/rules.d/99-caretas-webcam.rules > /dev/null
        $SUDO udevadm control --reload-rules 2>/dev/null || true
        $SUDO usermod -aG video "$TARGET_USER"
        say "pronto. Agora rode: ./scripts/camera_wsl.sh bind (uma vez, aceite a janela de Administrador)"
        ;;

    bind)
        need_usbipd
        pick_camera
        # --force: o Windows deixa de usar a câmera (necessário quando ela tem microfone ou
        # algum programa a mantém ocupada: "Device busy"). Desfazer: ./scripts/camera_wsl.sh unbind
        FORCE=""
        [ "${2:-}" = "--force" ] && FORCE=" --force"
        say "abrindo pedido de Administrador no Windows para compartilhar a câmera $HWID${FORCE}..."
        (cd /mnt/c && powershell.exe -NoProfile -Command \
            "Start-Process -FilePath usbipd -ArgumentList 'bind --hardware-id $HWID$FORCE' -Verb RunAs -Wait") || true
        say "situação: $(state || true)"
        ;;

    attach)
        need_usbipd
        pick_camera
        lsmod | grep -q uvcvideo || sudo -n modprobe uvcvideo 2>/dev/null || true
        if autoattach_running && has_video; then
            say "já conectada: $(ls /dev/video* | tr '\n' ' ')"
            exit 0
        fi
        st=$(state || true)
        case "$st" in
            "")
                say "nenhuma câmera do config (${HWIDS% }) aparece no Windows (desconectada? outro modelo? veja 'usbipd list')"
                exit 1 ;;
            *"Not shared"*)
                say "a câmera ainda não foi compartilhada. Rode UMA VEZ: ./scripts/camera_wsl.sh bind"
                exit 1 ;;
        esac
        autoattach_running && kill "$(cat "$PIDFILE")" 2>/dev/null
        # --auto-attach: se a câmera cair (cabo, USB), o usbipd reconecta sozinho enquanto o jogo roda.
        (cd /mnt/c && nohup "$USBIPD" attach --wsl --hardware-id "$HWID" --auto-attach > /tmp/caretas-usbipd.log 2>&1 &
         echo $! > "$PIDFILE")
        if wait_video 60; then
            say "conectada: $(ls /dev/video* | tr '\n' ' ')"
        else
            say "não apareceu /dev/video* em 30 s. Log: /tmp/caretas-usbipd.log"
            if grep -q "Failed to attach" /tmp/caretas-usbipd.log 2>/dev/null; then
                say "o Windows está segurando a câmera. Rode UMA VEZ: ./scripts/camera_wsl.sh bind --force"
            fi
            exit 1
        fi
        ;;

    detach)
        need_usbipd
        pick_camera
        autoattach_running && kill "$(cat "$PIDFILE")" 2>/dev/null
        rm -f "$PIDFILE"
        (cd /mnt/c && "$USBIPD" detach --hardware-id "$HWID") 2>/dev/null || true
        say "câmera devolvida ao Windows"
        ;;

    unbind)
        need_usbipd
        pick_camera
        autoattach_running && kill "$(cat "$PIDFILE")" 2>/dev/null
        rm -f "$PIDFILE"
        say "abrindo pedido de Administrador para devolver a câmera $HWID ao Windows..."
        (cd /mnt/c && powershell.exe -NoProfile -Command \
            "Start-Process -FilePath usbipd -ArgumentList 'unbind --hardware-id $HWID' -Verb RunAs -Wait") || true
        say "situação: $(state || true)"
        ;;

    *)
        sed -n '2,13p' "$0"
        exit 2 ;;
esac
