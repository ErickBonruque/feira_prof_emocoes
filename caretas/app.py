"""Laço principal: janela, teclado, e a cola entre câmera, processamento, jogo e tela."""

from __future__ import annotations

import glob
import hashlib
import logging
import os
import platform
import sys
import time
import warnings

from . import offline
from .config import PROJECT_ROOT, Config, ConfigError, load_config

log = logging.getLogger("caretas")

KEYS_HELP = ("Enter/Espaço próximo | S/N revisão (a IA acertou?) | R reinicia | E modo explicação | "
             "M som | F/F11 tela cheia | D/F1 debug | C troca câmera | Q/Esc 2x sai")
NEXT_KEYS = ("K_RETURN", "K_KP_ENTER", "K_SPACE", "K_PAGEDOWN", "K_RIGHT")
YES_KEYS = ("K_s", "K_y", "K_UP")
NO_KEYS = ("K_n", "K_DOWN")
QUIT_CONFIRM_SECONDS = 2.5


def _open_display(pygame, cfg: Config, fullscreen: bool):
    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode(tuple(cfg.ui.window_size), pygame.RESIZABLE)
    return screen


def _keys(pygame, names) -> set[int]:
    return {getattr(pygame, n) for n in names}


def run(args) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"\n[ERRO] config.yaml: {exc}\n", file=sys.stderr)
        return 2
    if args.camera is not None:
        cfg.camera.index = args.camera
        cfg.camera.usb_hardware_id = ""  # índice explícito: não escolhe pelo VID:PID (Windows)
    if args.windowed:
        cfg.ui.fullscreen = False
    if cfg.privacy.block_network:
        offline.install()

    if args.check:
        return self_check(cfg, args)
    if args.list_cameras:
        return list_cameras(cfg)

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    from .capture import Camera
    from .detection import FaceDetector
    from .emotion import EmotionModel
    from .game import ACTIVE, Game, Phase
    from .pipeline import Processor
    from .ui.debug import DebugOverlay
    from .ui.lab import LabView
    from .ui.renderer import Renderer
    from .ui.sound import SoundBoard

    warnings.filterwarnings("ignore", message="Requested window was forcibly resized")
    if platform.system() == "Windows":
        _windows_dpi_aware()
    if cfg.audio.enabled:
        pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption(cfg.ui.title)
    fullscreen = cfg.ui.fullscreen
    screen = _open_display(pygame, cfg, fullscreen)
    renderer = Renderer(cfg, screen)
    renderer.draw_splash("CARREGANDO OS MODELOS DE IA...", time.monotonic())
    pygame.display.flip()
    pygame.event.pump()

    camera = Camera(cfg.camera, args.video)
    camera.start()
    detector = FaceDetector(cfg.resolve_path(cfg.detector.model), cfg.detector.input_width,
                            cfg.detector.score_threshold)
    emotion = EmotionModel(cfg.resolve_path(cfg.emotion.model), cfg.emotion.device)
    log.info("modelo de emoção rodando em %s", emotion.device_label)
    processor = Processor(cfg, camera, detector, emotion)
    processor.start()

    game = Game(cfg, time.monotonic())
    debug = DebugOverlay(cfg)
    lab = LabView(cfg, renderer)
    sounds = SoundBoard(cfg)
    next_keys, yes_keys, no_keys = _keys(pygame, NEXT_KEYS), _keys(pygame, YES_KEYS), _keys(pygame, NO_KEYS)
    show_debug = bool(args.debug)
    lab_mode = False
    clock = pygame.time.Clock()
    started = time.monotonic()
    next_stats = started + 10.0
    log.info("pronto! %s", KEYS_HELP)

    quit_armed_at = -10.0
    errors: list[float] = []
    try:
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    k = ev.key
                    if k in (pygame.K_ESCAPE, pygame.K_q):
                        # Duas vezes seguidas para sair: uma tecla apertada sem querer não fecha o jogo.
                        t = time.monotonic()
                        if t - quit_armed_at < QUIT_CONFIRM_SECONDS:
                            running = False
                        else:
                            quit_armed_at = t
                            renderer.toast("APERTE Q OU ESC DE NOVO PARA SAIR", t, QUIT_CONFIRM_SECONDS)
                    elif k in next_keys and not lab_mode:
                        game.advance(time.monotonic())
                    elif k in yes_keys or k in no_keys:
                        game.review(k in yes_keys, time.monotonic())
                    elif k == pygame.K_r:
                        game.reset(time.monotonic(), "manual")
                    elif k == pygame.K_e:
                        # Modo explicação: pausa o jogo e mostra a IA por dentro. Voltar reinicia a partida.
                        lab_mode = not lab_mode
                        lab.reset()
                        game.reset(time.monotonic(), "lab" if lab_mode else "lab_exit")
                    elif k == pygame.K_m:
                        on = sounds.toggle()
                        msg = "SOM DESLIGADO" if not on else ("SOM LIGADO" if sounds.available else "SEM SAÍDA DE SOM")
                        renderer.toast(msg, time.monotonic(), 1.5)
                    elif k in (pygame.K_f, pygame.K_F11):
                        fullscreen = not fullscreen
                        screen = _open_display(pygame, cfg, fullscreen)
                        renderer.set_screen(screen)
                    elif k in (pygame.K_d, pygame.K_F1):
                        show_debug = not show_debug
                    elif k == pygame.K_c and not args.video:
                        camera.next_camera()
                        game.reset(time.monotonic(), "camera_switch")
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and game.phase == Phase.REPORT:
                    # Os botões do relatório também funcionam com o mouse.
                    for name, rect in renderer.report_view.buttons.items():
                        if rect.collidepoint(ev.pos):
                            if name == "next":
                                game.advance(time.monotonic())
                            else:
                                game.review(name == "yes", time.monotonic())
                            break
                elif ev.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED) and not fullscreen:
                    screen = pygame.display.get_surface()
                    renderer.set_screen(screen)

            now = time.monotonic()
            result = processor.latest()
            try:
                if game.phase in ACTIVE and not camera.healthy() and camera.last_frame_age() > cfg.detector.lost_seconds:
                    game.reset(now, "camera")
                if not lab_mode:
                    game.update(result, now)
                req = game.take_release_request()
                if req is not None:
                    processor.request_release(req)

                # Cursor só aparece onde há botão para clicar (relatório) ou em janela.
                pygame.mouse.set_visible(not fullscreen or game.phase == Phase.REPORT)
                if lab_mode:
                    lab.draw(screen, now, result, camera, emotion.device_label)
                    renderer.draw_overlays(now)
                else:
                    renderer.draw(now, game, result, camera)
                    sounds.update(game, now)
                if show_debug:
                    debug.draw(screen, renderer, now, game, result, camera, processor,
                               emotion.device_label, clock.get_fps())
            except Exception:  # noqa: BLE001 - no evento, um quadro com erro não pode derrubar o jogo
                errors = [t for t in errors if now - t < 10.0] + [now]
                if len(errors) <= 3:
                    log.exception("erro no quadro (o jogo continua)")
                if len(errors) >= 50:  # erro persistente: reinicia a partida para sair do estado ruim
                    log.error("erros repetidos; reiniciando a partida")
                    game.reset(now, "error")
                    errors.clear()
            pygame.display.flip()
            clock.tick(cfg.ui.fps_limit)

            if now >= next_stats:
                next_stats = now + 30.0
                timings = result.timings if result is not None else {}
                log.info("desempenho: tela %.0f fps | câmera %.0f fps | processamento %.0f fps | "
                         "detecção %.1f ms | emoção %.1f ms (%s) | fase %s",
                         clock.get_fps(), camera.fps, processor.fps, timings.get("detect_ms", 0.0),
                         timings.get("emotion_ms", 0.0), emotion.device_label, game.phase.value)
            if args.exit_after and now - started > args.exit_after:
                log.info("encerrando após %.0fs (--exit-after)", args.exit_after)
                running = False
    finally:
        processor.stop()
        camera.stop()
        pygame.quit()
    if offline.blocked_attempts:
        log.error("tentativas de rede bloqueadas: %s", offline.blocked_attempts)
    return 0


# ---------------------------------------------------------------------- utilitários
def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _windows_dpi_aware() -> None:
    """Sem isto, com escala de 125/150% o Windows amplia a janela e a tela cheia sai borrada/cortada."""
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # por monitor
    except Exception:  # noqa: BLE001 - versões antigas do Windows
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def _list_cameras_windows(cfg: Config) -> int:
    import cv2

    from .win_camera import allowed_devices, list_devices, parse_hardware_ids

    hwids = parse_hardware_ids(cfg.camera.usb_hardware_id)
    devices = list_devices()
    # Lista vazia = usa o índice fixo (camera.index ou --camera N)
    allowed = allowed_devices(devices, hwids) if hwids else [d for d in devices if d.index == cfg.camera.index]
    print(f"câmeras do DirectShow (lista do config: {', '.join(hwids) or f'vazia, usa o índice {cfg.camera.index}'}):")
    for d in devices:
        if d in allowed:
            tag = "USADA PELO JOGO" if d == allowed[0] else f"reserva {allowed.index(d)}"
        else:
            tag = "fora da lista, ignorada" if hwids else "não usada"
        print(f"  [{d.index}] {d.name}  {d.hwid or '(sem VID:PID)'}  -> {tag}")
    if not allowed:
        print("  nenhuma câmera da lista conectada" if hwids else f"  nenhuma câmera no índice {cfg.camera.index}")
        print('  dica: coloque o VID:PID da sua câmera em camera.usb_hardware_id no config.yaml,')
        print('        ou rode com --camera N usando o número entre colchetes acima')
        return 1
    # Confere só a escolhida (as fora da lista, como a integrada, nem são abertas). Nada é salvo.
    from .capture import Camera

    cam = Camera(cfg.camera)
    cap = cam._open()
    ok, frame = cap.read() if cap is not None else (False, None)
    fcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace") if cap else "?"
    print(f"  {cam.source_label}: {'OK ' + str(frame.shape[1]) + 'x' + str(frame.shape[0]) + ' ' + fcc if ok else 'não entrega imagem'}")
    if cap is not None:
        cap.release()
    del frame
    return 0 if ok else 1


def list_cameras(cfg: Config) -> int:
    import cv2

    if platform.system() == "Windows":
        return _list_cameras_windows(cfg)
    if platform.system() == "Linux":
        devs = sorted(glob.glob("/dev/video*"))
        print("dispositivos:", ", ".join(devs) if devs else "nenhum /dev/video* (webcam não repassada ao WSL?)")
        indices = [int(d.replace("/dev/video", "")) for d in devs if d[10:].isdigit()]
        backend = cv2.CAP_V4L2
    else:
        indices, backend = list(range(5)), cv2.CAP_ANY
    found = 0
    for i in indices:
        cap = cv2.VideoCapture(i, backend)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        if ok and frame is not None:
            found += 1
            print(f"  câmera {i}: OK {frame.shape[1]}x{frame.shape[0]}")
        else:
            print(f"  câmera {i}: não entrega imagem")
        cap.release()
    return 0 if found else 1


def self_check(cfg: Config, args) -> int:
    """Checklist automático do dia do evento: tudo local, nada de rede."""
    import numpy as np

    from .manifest import ASSETS

    ok_all = True

    def report(ok: bool, what: str, detail: str = "") -> None:
        nonlocal ok_all
        ok_all &= ok
        print(f"  [{'OK' if ok else 'FALHOU'}] {what}{(' - ' + detail) if detail else ''}")

    print(f"\nJOGO DAS CARETAS - verificação ({platform.system()} {platform.release()}, Python {platform.python_version()})")
    report(True, "config.yaml válido")
    report(offline.blocked_attempts == [] and cfg.privacy.block_network, "bloqueio de rede ativo")
    for rel, _url, sha in ASSETS:
        p = PROJECT_ROOT / rel
        if not p.exists():
            report(False, rel, "faltando (rode o setup com internet)")
        else:
            report(_sha256(p) == sha, rel, "hash confere" if _sha256(p) == sha else "hash diferente!")

    try:
        from .detection import FaceDetector
        from .emotion import EmotionModel

        det = FaceDetector(cfg.resolve_path(cfg.detector.model), cfg.detector.input_width)
        img = np.zeros((cfg.camera.height, cfg.camera.width, 3), np.uint8)
        t = time.perf_counter()
        for _ in range(10):
            det.detect(img)
        report(True, "detector de rosto (YuNet)", f"{(time.perf_counter() - t) * 100:.1f} ms/quadro")
        emo = EmotionModel(cfg.resolve_path(cfg.emotion.model), cfg.emotion.device)
        face = np.full((224, 224, 3), 128, np.uint8)
        t = time.perf_counter()
        for _ in range(20):
            emo.predict(face)
        want_gpu = cfg.emotion.device in ("auto", "cuda")
        gpu_ok = emo.provider == "CUDAExecutionProvider" or not want_gpu
        report(True, "modelo de emoção (HSEmotion)", f"{emo.device_label}, {(time.perf_counter() - t) * 50:.1f} ms/rosto")
        if not gpu_ok:
            print("         aviso: GPU indisponível, rodando na CPU (funciona, só usa mais processador)")
    except Exception as exc:  # noqa: BLE001
        report(False, "modelos de IA", str(exc))

    if args.video:
        report(os.path.exists(args.video), f"vídeo de teste {args.video}")
    else:
        import cv2

        from .capture import Camera

        cam = Camera(cfg.camera)
        cap = cam._open()
        if cap is None:
            hint = ""
            if platform.system() == "Linux" and not glob.glob("/dev/video*"):
                hint = "nenhum /dev/video*: rode ./scripts/camera_wsl.sh attach (ver README)"
            report(False, cam.source_label, hint or cam._open_error or "não abriu")
        else:
            n, t = 0, time.perf_counter()
            frame = None
            while n < 30 and time.perf_counter() - t < 5:
                okf, frame = cap.read()
                n += int(bool(okf))
            fps = n / max(1e-6, time.perf_counter() - t)
            shape = f"{frame.shape[1]}x{frame.shape[0]}" if frame is not None else "?"
            fcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace").strip()
            report(n > 0, cam.source_label, f"{shape} {fcc} ~{fps:.0f} FPS")
            cap.release()
            del frame

    if platform.system() == "Linux":
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        report(has_display, "tela gráfica (WSLg)", os.environ.get("DISPLAY", "") or "sem DISPLAY")
    print("\nTUDO PRONTO!\n" if ok_all else "\nHÁ PROBLEMAS - veja a seção 'Problemas comuns' do README.\n")
    return 0 if ok_all else 1
