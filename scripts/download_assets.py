"""Baixa modelos e fontes para dentro do projeto (única etapa que usa internet).

Confere o SHA-256 de cada arquivo; se já existir e estiver íntegro, não baixa de novo.
Uso: .venv/bin/python scripts/download_assets.py
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from caretas.manifest import ASSETS, LICENSES  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "jogo-das-caretas-setup"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


def main() -> int:
    failed = 0
    for rel, url, digest in ASSETS:
        dest = ROOT / rel
        if dest.exists() and sha256(dest) == digest:
            print(f"  [ok]      {rel}")
            continue
        print(f"  [baixando] {rel}")
        for attempt in range(3):
            try:
                fetch(url, dest)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"      tentativa {attempt + 1} falhou: {exc}")
        if dest.exists() and sha256(dest) == digest:
            print(f"  [ok]      {rel}")
        else:
            print(f"  [ERRO]    {rel}: download falhou ou hash diferente")
            failed += 1
    for rel, url in LICENSES:
        dest = ROOT / rel
        if not dest.exists():
            try:
                fetch(url, dest)
            except Exception as exc:  # noqa: BLE001
                print(f"  [aviso]   licença {rel} não baixada: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
