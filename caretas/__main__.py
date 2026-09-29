"""python -m caretas [--debug] [--windowed] [--camera N] [--video ARQ] [--check] [--list-cameras]"""

import argparse
import logging
import os
import sys

# Antes de importar o OpenCV: sem avisos repetidos enquanto a câmera reconecta
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from .app import KEYS_HELP, run  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(prog="caretas", description="Jogo das Caretas - reconhecimento de emoções",
                                epilog=f"Teclas: {KEYS_HELP}")
    p.add_argument("--config", help="arquivo de configuração (padrão: config.yaml do projeto)")
    p.add_argument("--debug", action="store_true", help="começa com o painel de debug aberto")
    p.add_argument("--windowed", action="store_true", help="abre em janela em vez de tela cheia")
    p.add_argument("--camera", type=int, help="índice da câmera (sobrescreve o config)")
    p.add_argument("--video", help="usa um arquivo de vídeo em loop no lugar da câmera (só para testes)")
    p.add_argument("--check", action="store_true", help="verifica modelos, GPU, câmera e sai")
    p.add_argument("--list-cameras", action="store_true", help="lista as câmeras encontradas e sai")
    p.add_argument("--exit-after", type=float, help=argparse.SUPPRESS)  # testes automatizados
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stdout)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
