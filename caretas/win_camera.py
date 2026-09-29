"""Câmeras do DirectShow no Windows, escolhidas pelo VID:PID (sem dependência extra: só ctypes).

O índice que o OpenCV usa em CAP_DSHOW é a posição da câmera nesta mesma enumeração, e ele
muda quando alguém tira e recoloca uma câmera. Por isso o jogo nunca usa um número fixo: a cada
(re)conexão lista os dispositivos, lê o `vid_XXXX&pid_XXXX` do caminho de cada um e usa a
primeira câmera de `camera.usb_hardware_id` que estiver conectada. Câmeras fora da lista (a
integrada do notebook, câmeras virtuais como a do OBS) nunca são usadas.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

_HWID_RE = re.compile(r"([0-9a-fA-F]{4}):([0-9a-fA-F]{4})")
_PATH_RE = re.compile(r"vid_([0-9a-f]{4})&pid_([0-9a-f]{4})", re.IGNORECASE)


@dataclass(frozen=True)
class DShowDevice:
    index: int   # índice para cv2.VideoCapture(index, cv2.CAP_DSHOW)
    name: str
    path: str

    @property
    def hwid(self) -> str | None:
        return hwid_from_path(self.path)


def parse_hardware_ids(text: str) -> list[str]:
    """ "046d:082d, 1bcf:28c4" -> ["046d:082d", "1bcf:28c4"] (minúsculas, na ordem de preferência)."""
    seen: list[str] = []
    for vid, pid in _HWID_RE.findall(text or ""):
        hwid = f"{vid}:{pid}".lower()
        if hwid not in seen:
            seen.append(hwid)
    return seen


def hwid_from_path(path: str) -> str | None:
    m = _PATH_RE.search(path or "")
    return f"{m.group(1)}:{m.group(2)}".lower() if m else None


def allowed_devices(devices: list[DShowDevice], hwids: list[str]) -> list[DShowDevice]:
    """Só as câmeras da lista, na ordem de preferência da lista (e não na ordem do Windows)."""
    return [d for hwid in hwids for d in devices if d.hwid == hwid]


# ---------------------------------------------------------------------- COM (DirectShow)
def list_devices() -> list[DShowDevice]:
    """Câmeras de vídeo do DirectShow, na ordem dos índices do OpenCV. Lista vazia se falhar."""
    try:
        return _enumerate()
    except OSError as exc:
        log.warning("não consegui listar as câmeras do DirectShow: %s", exc)
        return []


def _enumerate() -> list[DShowDevice]:
    import ctypes
    import uuid
    from ctypes import POINTER, WINFUNCTYPE, byref, c_long, c_ulong, c_void_p, c_wchar_p

    class GUID(ctypes.Structure):
        _fields_ = [("b", ctypes.c_ubyte * 16)]

    def guid(s: str) -> GUID:
        g = GUID()
        ctypes.memmove(byref(g), uuid.UUID(s).bytes_le, 16)
        return g

    class VARIANT(ctypes.Structure):  # 24 bytes no Windows 64 bits
        _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                    ("r3", ctypes.c_ushort), ("val", c_void_p), ("pad", c_void_p)]

    ole32 = ctypes.WinDLL("ole32")
    oleaut32 = ctypes.WinDLL("oleaut32")
    ole32.CoCreateInstance.restype = c_long
    ole32.CoCreateInstance.argtypes = (POINTER(GUID), c_void_p, c_ulong, POINTER(GUID), POINTER(c_void_p))
    ole32.CoInitializeEx.restype = c_long
    ole32.CoInitializeEx.argtypes = (c_void_p, c_ulong)
    oleaut32.VariantClear.argtypes = (POINTER(VARIANT),)

    def call(obj, idx, *args, argtypes=()):
        vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
        return WINFUNCTYPE(c_long, c_void_p, *argtypes)(vtbl[idx])(obj, *args)

    def release(obj):
        if obj:
            vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
            WINFUNCTYPE(c_ulong, c_void_p)(vtbl[2])(obj)

    def read_prop(bag, name: str) -> str:
        v = VARIANT()
        # IPropertyBag::Read
        if call(bag, 3, name, byref(v), None, argtypes=(c_wchar_p, POINTER(VARIANT), c_void_p)) != 0:
            return ""
        s = ctypes.wstring_at(v.val) if v.vt == 8 and v.val else ""  # VT_BSTR
        oleaut32.VariantClear(byref(v))
        return s

    # S_OK/S_FALSE: precisamos desfazer; RPC_E_CHANGED_MODE: a thread já tem COM, só usamos.
    hr_init = ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
    devices: list[DShowDevice] = []
    dev_enum, enum_mk = c_void_p(), c_void_p()
    try:
        hr = ole32.CoCreateInstance(byref(guid("62BE5D10-60EB-11d0-BD3B-00A0C911CE86")), None, 1,  # SystemDeviceEnum
                                    byref(guid("29840822-5B84-11D0-BD3B-00A0C911CE86")), byref(dev_enum))
        if hr != 0:
            raise OSError(f"CoCreateInstance falhou (0x{hr & 0xFFFFFFFF:08x})")
        # ICreateDevEnum::CreateClassEnumerator(VideoInputDeviceCategory); S_FALSE = nenhuma câmera
        hr = call(dev_enum, 3, byref(guid("860BB310-5D01-11d0-BD3B-00A0C911CE86")), byref(enum_mk), 0,
                  argtypes=(POINTER(GUID), POINTER(c_void_p), c_ulong))
        if hr != 0 or not enum_mk:
            return devices
        iid_bag = guid("55272A00-42CB-11CE-8135-00AA004BB851")
        moniker, fetched = c_void_p(), c_ulong()
        while call(enum_mk, 3, 1, byref(moniker), byref(fetched),  # IEnumMoniker::Next
                   argtypes=(c_ulong, POINTER(c_void_p), POINTER(c_ulong))) == 0 and fetched.value:
            bag = c_void_p()
            name = path = ""
            # IMoniker::BindToStorage -> IPropertyBag
            if call(moniker, 9, None, None, byref(iid_bag), byref(bag),
                    argtypes=(c_void_p, c_void_p, POINTER(GUID), POINTER(c_void_p))) == 0:
                name, path = read_prop(bag, "FriendlyName"), read_prop(bag, "DevicePath")
                release(bag)
            devices.append(DShowDevice(len(devices), name, path))
            release(moniker)
            moniker = c_void_p()
    finally:
        release(enum_mk)
        release(dev_enum)
        if hr_init in (0, 1):
            ole32.CoUninitialize()
    return devices
