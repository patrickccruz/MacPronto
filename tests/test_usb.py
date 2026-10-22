from __future__ import annotations

import plistlib

import pytest

from macpronto.usb import windows
from macpronto.usb.mapper import UsbMapSession, hexswap

HUB = "USB#ROOT_HUB30#4&1&0&0#{f18a0e88-c30c-11d0-8815-00a0c906bed8}"
INSTANCE = r"PCI\VEN_8086&DEV_A36D&SUBSYS_50071458&REV_10\3&11583659&0&A0"


def port(index, speed, devices=(), companion=0, user=True):
    return {
        "index": index,
        "status": "DeviceConnected" if devices else "NoDeviceConnected",
        "class": speed,
        "type_c": False,
        "user_connectable": user,
        "companion_info": {"port": companion, "hub": HUB if companion else "", "multiple_companions": False},
        "devices": [{"name": name, "vid_pid": "0000:0000", "speed": speed, "devices": []} for name in devices],
    }


def controller(ports):
    return {
        "name": INSTANCE,
        "identifiers": {"instance_id": INSTANCE, "pci_id": ["8086", "a36d"]},
        "hub_name": HUB,
        "class": None,
        "ports": ports,
    }


def properties(_instance_id):
    return {"name": "Intel USB 3.1 XHCI", "acpi_path": r"\_SB.PCI0.XHC", "bdf": [0, 20, 0], "class": 0x30}


@pytest.fixture
def session(tmp_path):
    snapshots = [
        controller(
            [
                port(1, 2, ["Teclado"], companion=3),
                port(2, 2, ["Intel(R) Wireless Bluetooth(R)"]),
                port(3, 3, [], companion=1),
                port(4, 3),
            ]
        ),
        # Segunda leitura: um pendrive USB 3 na porta 4 e o teclado desconectado
        controller(
            [
                port(1, 2, [], companion=3),
                port(2, 2, ["Intel(R) Wireless Bluetooth(R)"]),
                port(3, 3, [], companion=1),
                port(4, 3, ["Pendrive"]),
            ]
        ),
    ]
    reads = iter(snapshots)
    return UsbMapSession(f"teste-{tmp_path.name}", reader=lambda: [next(reads)], properties=properties)


def by_name(state):
    return {p["name"]: p for p in state["controllers"][0]["ports"]}


def test_mescla_e_selecao_automatica(session):
    session.refresh()
    ports = by_name(session.refresh())
    # HS01 teve o teclado; SS01 é o par USB 3 dela; SS02 recebeu o pendrive; HS02 é o Bluetooth
    assert ports["HS01"]["selected"] and ports["SS01"]["selected"]
    assert ports["SS02"]["selected"]
    assert ports["HS02"]["type"] == 255
    assert ports["HS01"]["type"] == 3 and ports["SS01"]["type"] == 3
    assert [d["name"] for d in ports["HS01"]["seen"]] == ["Teclado"]
    assert ports["HS01"]["current"] == []


def test_par_de_portas_muda_junto(session):
    session.refresh()
    state = session.update_port(INSTANCE, 1, {"selected": False, "type": 9})
    ports = by_name(state)
    assert not ports["HS01"]["selected"] and not ports["SS01"]["selected"]
    assert ports["SS01"]["type"] == 9 and not ports["SS01"]["type_guessed"]


def test_limite_de_15_portas(tmp_path):
    many = controller([port(i, 2, ["Dispositivo"]) for i in range(1, 18)])
    session = UsbMapSession(f"limite-{tmp_path.name}", reader=lambda: [many], properties=properties)
    state = session.refresh()
    assert state["errors"] and "15" in state["errors"][0]
    with pytest.raises(ValueError):
        session.build_kext(tmp_path)


def test_kext_gerado(session, tmp_path):
    session.refresh()
    session.refresh()
    kext = session.build_kext(tmp_path)
    info = plistlib.loads((kext / "Contents" / "Info.plist").read_bytes())
    personality = info["IOKitPersonalities"]["XHC"]
    assert personality["IONameMatch"] == "XHC"
    assert info["OSBundleLibraries"] == {"com.dhinakg.USBToolBox.kext": "1.0.0"}
    ports = personality["IOProviderMergeProperties"]["ports"]
    assert set(ports) == {"HS01", "HS02", "SS01", "SS02"}
    assert ports["SS02"]["port"] == hexswap(4) == bytes([4, 0, 0, 0])
    assert ports["HS02"]["UsbConnector"] == 255
    assert personality["IOProviderMergeProperties"]["port-count"] == bytes([4, 0, 0, 0])


def test_caminho_da_controladora():
    path = r"\\?\pci#ven_8086&dev_06ed&subsys_316c17aa&rev_00#3&11583659&0&a0#{3abf6f2d-71c4-462a-8a92-1e6861e6af27}"
    assert windows.instance_id_from_path(path) == r"PCI\VEN_8086&DEV_06ED&SUBSYS_316C17AA&REV_00\3&11583659&0&A0"
