# Webcam

A webcam é o que mais dá problema quando o jogo roda num computador novo. Este guia mostra como fazer o jogo achar a sua câmera e o que fazer quando ela não funciona.

Sempre que pedir ajuda, mande a saída de `--list-cameras` e de `--check`: com ela dá para saber o que está errado.

---

## Windows

### Por que o jogo não acha a minha câmera?

Por padrão, o `config.yaml` só aceita as duas webcams usadas no evento (Logitech C920 e WEMISS), para o jogo nunca abrir a câmera errada do notebook durante a feira. **No seu PC, provavelmente a sua câmera não está nessa lista**, e o jogo mostra "CÂMERA DESCONECTADA" ou `nenhuma câmera da lista conectada`.

### 1. Veja quais câmeras o jogo enxerga

```bat
start_windows.bat --list-cameras
```

A saída é parecida com esta:

```
câmeras do DirectShow (lista do config: 046d:082d, 1bcf:28c4):
  [0] Integrated Camera  5986:211b  -> fora da lista, ignorada
  [1] OBS Virtual Camera  (sem VID:PID)  -> fora da lista, ignorada
  nenhuma câmera da lista conectada
```

O número entre colchetes é o **índice** e o `xxxx:xxxx` é o **VID:PID** (a "identidade" da câmera).

### 2. Diga ao jogo qual câmera usar

- **Jeito fixo (recomendado):** abra o `config.yaml` no Bloco de Notas e troque a linha `usb_hardware_id` pelo VID:PID da sua câmera:

  ```yaml
    usb_hardware_id: "5986:211b"
  ```

  Assim o jogo acha a câmera mesmo que o Windows mude a numeração (isso acontece quando uma câmera é tirada e recolocada). Dá para listar várias, separadas por vírgula: o jogo usa a primeira conectada e a tecla **C** alterna entre elas.

- **Jeito rápido:** use o índice direto, sem editar nada:

  ```bat
  start_windows.bat --camera 0
  ```

  Ou deixe a lista vazia (`usb_hardware_id: ""`) para o jogo usar sempre o `camera.index` do `config.yaml`. Se a câmera não tiver VID:PID (câmeras virtuais, algumas integradas), este é o único jeito.

### 3. Confira

```bat
start_windows.bat --check
```

A linha da câmera deve aparecer como `[OK]`, com a resolução e o FPS.

### Se ainda não funcionar

| Sintoma | O que fazer |
|---|---|
| Nenhuma câmera aparece na lista | Veja se ela aparece no app **Câmera** do Windows. Se não aparecer lá, é driver, cabo ou porta USB. Em notebooks, confira a tecla de desligar a câmera (ícone de câmera riscada, geralmente em F8/F10) ou a tampinha física. |
| A câmera aparece, mas "não entrega imagem" ou a tela fica preta | **Configurações → Privacidade e segurança → Câmera**: ligue **"Acesso à câmera"** e **"Permitir que aplicativos da área de trabalho acessem a câmera"**. Sem isso o Windows entrega só quadros pretos. |
| Funcionava e parou, ou "câmera em uso" | Feche Teams, Zoom, Discord, OBS, o app Câmera e abas do navegador em videochamada: só um programa pode usar a webcam por vez. |
| O jogo pegou a câmera errada | Coloque o VID:PID da câmera certa em `usb_hardware_id`, ou aperte **C** durante o jogo. |

---

## Linux

No Linux, a câmera é escolhida pelo **índice** (`/dev/video0` = índice 0). A lista `usb_hardware_id` é ignorada.

### 1. Veja quais câmeras existem

```bash
.venv/bin/python -m caretas --list-cameras
```

Mostra os `/dev/video*` e quais entregam imagem. Para ver os nomes das câmeras: `v4l2-ctl --list-devices` (pacote `v4l-utils`).

### 2. Escolha a câmera

Use o índice que entregou imagem: `./start.sh --camera 2`, ou fixe em `camera.index` no `config.yaml`. A tecla **C** troca de câmera durante o jogo.

É comum cada webcam criar **dois** dispositivos (`/dev/video0` e `/dev/video1`): o segundo é só de metadados e não entrega imagem. Use o primeiro.

### Se ainda não funcionar

| Sintoma | O que fazer |
|---|---|
| Nenhum `/dev/video*` | A câmera não foi detectada: veja `lsusb` e `dmesg | tail` logo depois de conectar. Troque de porta ou de cabo. |
| `Permission denied` no `/dev/video0` | Adicione seu usuário ao grupo `video`: `sudo usermod -aG video $USER`, depois saia da sessão e entre de novo. |
| "Câmera em uso" / não abre | Feche outros programas que usam a câmera (navegador em videochamada, OBS, Cheese). `fuser /dev/video0` mostra quem está usando. |

---

## Imagem e desempenho (Windows e Linux)

| Sintoma | O que fazer |
|---|---|
| Imagem escura ou jogo lento (a tecla **D** mostra o FPS da câmera) | Com pouca luz, a webcam alonga a exposição e perde FPS. Ilumine o rosto de frente. No Windows, se continuar, troque `exposure: auto` por `exposure: -6` no `config.yaml`. |
| Imagem esticada, cortada ou com cores estranhas | Algumas webcams não suportam MJPG ou 1280x720. No `config.yaml`, teste `fourcc: ""` e/ou `width: 640` e `height: 480`. |
| Imagem invertida | `camera.mirror: false` (o padrão espelha, como selfie). |

---

## Detalhes técnicos (Windows)

Já resolvidos no código (`caretas/capture.py` e `caretas/win_camera.py`); ficam aqui para quem for mexer:

- **Backend DirectShow.** O Media Foundation (MSMF) chegou a travar por minutos ao abrir a C920.
- **Escolha pelo VID:PID.** O índice do DirectShow muda quando uma câmera é tirada e recolocada. Por isso, a cada (re)conexão o jogo lista os dispositivos, lê o `vid_XXXX&pid_XXXX` do caminho de cada um e usa a primeira câmera da lista que estiver conectada.
- **Ordem da negociação.** No DirectShow, o MJPG só vale se for pedido *depois* da largura e da altura, e pedir o FPS depois disso volta para YUY2. A C920 em YUY2 a 1280x720 só dá **10 FPS**; em MJPG, 30 FPS.
- **Exposição.** `camera.exposure: auto` (padrão) religa a exposição automática sempre que abre a câmera, porque a exposição manual fica gravada na câmera depois que o jogo fecha.
