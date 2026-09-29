"""Tokens visuais (inspirados no DESIGN.md "The Verge", ver docs/DESIGN.md).

Canvas quase preto, acentos "fita de perigo" menta + ultravioleta, blocos de cor
saturada, tipografia display gigante (Anton) e rótulos mono em CAIXA ALTA.
Sem gradientes e sem sombras: contraste vem de blocos sólidos e bordas.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from ..config import PROJECT_ROOT

# ----------------------------------------------------------------- cores
CANVAS = (19, 19, 19)          # #131313
SLATE = (45, 45, 45)           # #2d2d2d
FRAME = (49, 49, 49)           # #313131
WHITE = (255, 255, 255)
MUTED = (233, 233, 233)
GRAY = (148, 148, 148)         # #949494
BLACK = (0, 0, 0)
MINT = (60, 255, 208)          # #3cffd0 jelly mint
MINT_DARK = (48, 152, 117)     # #309875
UV = (82, 0, 255)              # #5200ff ultraviolet
UV_DARK = (61, 0, 191)         # #3d00bf
YELLOW = (255, 222, 0)
PINK = (255, 61, 139)
ORANGE = (255, 106, 0)
RED = (255, 59, 48)
TEAR = (120, 200, 255)

# ----------------------------------------------------------------- emoções
EMOTIONS = {
    "happiness": {
        "name": "FELIZ", "noun": "FELICIDADE", "color": YELLOW, "ink": BLACK,
        "prompt": "FAÇA CARA DE FELIZ!",
        "hint": "Sorria bem grande, mostrando os dentes!",
        "stamp": "QUE SORRISÃO!",
    },
    "surprise": {
        "name": "SURPRESA", "noun": "SURPRESA", "color": MINT, "ink": BLACK,
        "prompt": "FAÇA CARA DE SURPRESA!",
        "hint": "Olhos arregalados, sobrancelhas lá em cima e boca em O!",
        "stamp": "UAU!",
    },
    "sadness": {
        "name": "TRISTE", "noun": "TRISTEZA", "color": UV, "ink": WHITE,
        "prompt": "FAÇA CARA DE TRISTE!",
        "hint": "Sobrancelhas para cima no meio e boca para baixo, bem tristonho!",
        "stamp": "QUE DRAMA!",
    },
}

# Cor de cada uma das 8 classes do modelo (gráficos e barras). Triste usa o ultravioleta
# clareado para ter contraste como linha sobre o fundo escuro; nojo usa lima para não
# confundir com a menta da surpresa.
UV_LIGHT = (150, 110, 255)
LIME = (160, 220, 60)
CLASS_COLORS = {
    "anger": RED, "contempt": ORANGE, "disgust": LIME, "fear": PINK,
    "happiness": YELLOW, "neutral": MUTED, "sadness": UV_LIGHT, "surprise": MINT,
}

# ----------------------------------------------------------------- fontes
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
FONT_FILES = {
    "display": "Anton-Regular.ttf",        # substituto livre da Manuka
    "ui": "SpaceGrotesk-Bold.ttf",         # substituto livre da PolySans
    "ui_medium": "SpaceGrotesk-Medium.ttf",
    "mono": "SpaceMono-Bold.ttf",          # substituto livre da PolySans Mono
}
_FALLBACK = {"display": "impact", "ui": "arial", "ui_medium": "arial", "mono": "couriernew"}
_font_cache: dict[tuple[str, int], pygame.font.Font] = {}


def font(kind: str, size: int) -> pygame.font.Font:
    size = max(8, int(size))
    key = (kind, size)
    f = _font_cache.get(key)
    if f is None:
        path = FONT_DIR / FONT_FILES[kind]
        if Path(path).exists():
            f = pygame.font.Font(str(path), size)
        else:  # fonte não baixada: não trava o evento, usa a do sistema
            f = pygame.font.SysFont(_FALLBACK[kind], size, bold=kind != "ui_medium")
        _font_cache[key] = f
    return f
