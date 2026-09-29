import platform

import pytest

from caretas.config import ConfigError, load_config
from caretas.win_camera import DShowDevice, allowed_devices, hwid_from_path, parse_hardware_ids

INTEGRADA = DShowDevice(0, "HD Webcam", r"\\?\usb#vid_5986&pid_211b&mi_00#6&18b1eb6f&0&0000#{65e8773d}\global")
C920 = DShowDevice(1, "HD Pro Webcam C920", r"\\?\usb#vid_046d&pid_082d&mi_00#6&29f83ccd&0&0000#{65e8773d}\global")
OBS = DShowDevice(2, "OBS Virtual Camera", "")
WEMISS = DShowDevice(3, "WEMISS CM-A1", r"\\?\USB#VID_1BCF&PID_28C4&MI_00#7&1a2b&0&0000#{65e8773d}\global")


def test_parse_hardware_ids_keeps_order_and_normalizes():
    assert parse_hardware_ids('"046d:082d, 1BCF:28C4"  # comentário') == ["046d:082d", "1bcf:28c4"]
    assert parse_hardware_ids("046d:082d,046d:082d") == ["046d:082d"]
    assert parse_hardware_ids("") == []


def test_hwid_from_device_path():
    assert C920.hwid == "046d:082d"
    assert WEMISS.hwid == "1bcf:28c4"  # caminho em maiúsculas
    assert OBS.hwid is None
    assert hwid_from_path("nada") is None


def test_only_listed_cameras_in_preference_order():
    devices = [INTEGRADA, WEMISS, OBS, C920]  # ordem do Windows != ordem de preferência
    hwids = parse_hardware_ids("046d:082d, 1bcf:28c4")
    assert allowed_devices(devices, hwids) == [C920, WEMISS]
    # sem a C920, cai para a WEMISS; a integrada e a virtual nunca entram
    assert allowed_devices([INTEGRADA, OBS, WEMISS], hwids) == [WEMISS]
    assert allowed_devices([INTEGRADA, OBS], hwids) == []


def test_exposure_config(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("camera:\n  exposure: -6\n", encoding="utf-8")
    assert load_config(p).camera.exposure == -6
    p.write_text("camera:\n  exposure: clara\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="exposure"):
        load_config(p)


@pytest.mark.skipif(platform.system() != "Windows", reason="DirectShow só existe no Windows")
def test_directshow_enumeration_runs():
    from caretas.win_camera import list_devices

    devices = list_devices()  # não abre nenhuma câmera: só lê nome e caminho
    assert [d.index for d in devices] == list(range(len(devices)))
