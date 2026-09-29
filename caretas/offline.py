"""Garante que o jogo não fale com a internet durante a execução.

Qualquer tentativa de conexão (TCP/UDP) ou de resolução de nome para fora da
própria máquina levanta erro na hora. Serve para privacidade (nada sai do PC)
e como prova de que o jogo roda sem rede: se algo tentasse baixar, quebraria
no teste, e não no meio do evento.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket

log = logging.getLogger(__name__)

_LOCAL_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", ""}
_installed = False
blocked_attempts: list[str] = []


class NetworkBlockedError(OSError):
    pass


def _is_local(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode(errors="ignore")
    host = str(host).strip("[]").lower()
    if host in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _deny(what: str) -> None:
    blocked_attempts.append(what)
    log.error("BLOQUEADO acesso de rede: %s", what)
    raise NetworkBlockedError(f"acesso de rede bloqueado pelo jogo (modo offline): {what}")


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    # Bibliotecas que respeitam estas variáveis nem tentam ir para a rede.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("NO_PROXY", "*")

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_sendto = socket.socket.sendto
    orig_getaddrinfo = socket.getaddrinfo

    def _check(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
            if not _is_local(address[0]):
                _deny(f"{address[0]}:{address[1]}")

    def connect(self, address):
        _check(self, address)
        return orig_connect(self, address)

    def connect_ex(self, address):
        _check(self, address)
        return orig_connect_ex(self, address)

    def sendto(self, data, *args):
        address = args[-1]
        _check(self, address)
        return orig_sendto(self, data, *args)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local(host):
            _deny(f"DNS {host}")
        return orig_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.getaddrinfo = getaddrinfo
    log.info("modo offline: conexões de rede externas bloqueadas")
