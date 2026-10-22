"""Leitura da topologia USB pelas IOCTLs de hub do Windows (usbioctl.h), via ctypes.

Devolve uma lista de controladoras PCI, cada uma com as portas do hub raiz e os
dispositivos conectados (dispositivos atrás de hubs externos entram na porta do hub).
"""

from __future__ import annotations

import ctypes
import logging
import re
import struct
import sys
import uuid
from ctypes import wintypes

log = logging.getLogger(__name__)

GUID_DEVINTERFACE_USB_HOST_CONTROLLER = "3abf6f2d-71c4-462a-8a92-1e6861e6af27"

# CTL_CODE(FILE_DEVICE_USB, função, METHOD_BUFFERED, FILE_ANY_ACCESS)
IOCTL_USB_GET_ROOT_HUB_NAME = 0x220408
IOCTL_USB_GET_NODE_INFORMATION = 0x220408
IOCTL_USB_GET_NODE_CONNECTION_NAME = 0x220414
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 0x220448
IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES = 0x220450
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2 = 0x22045C

GENERIC_WRITE = 0x40000000
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 3
DIGCF_PRESENT = 0x2
DIGCF_DEVICEINTERFACE = 0x10

CONNECTION_STATUS = {
    0: "NoDeviceConnected",
    1: "DeviceConnected",
    2: "DeviceFailedEnumeration",
    3: "DeviceGeneralFailure",
    4: "DeviceCausedOvercurrent",
    5: "DeviceNotEnoughPower",
    6: "DeviceNotEnoughBandwidth",
    7: "DeviceHubNestedTooDeeply",
    8: "DeviceInLegacyHub",
    9: "DeviceEnumerating",
    10: "DeviceReset",
}

# Velocidades no formato do USBToolBox (shared.USBDeviceSpeeds)
LOW_SPEED, FULL_SPEED, HIGH_SPEED, SUPER_SPEED, SUPER_SPEED_PLUS, UNKNOWN_SPEED = 0, 1, 2, 3, 4, 9999


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> GUID:
        value = uuid.UUID(text)
        guid = cls()
        guid.Data1, guid.Data2, guid.Data3 = value.fields[0], value.fields[1], value.fields[2]
        for index, byte in enumerate(value.bytes[8:]):
            guid.Data4[index] = byte
        return guid


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class USB_DEVICE_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("bLength", ctypes.c_ubyte),
        ("bDescriptorType", ctypes.c_ubyte),
        ("bcdUSB", ctypes.c_ushort),
        ("bDeviceClass", ctypes.c_ubyte),
        ("bDeviceSubClass", ctypes.c_ubyte),
        ("bDeviceProtocol", ctypes.c_ubyte),
        ("bMaxPacketSize0", ctypes.c_ubyte),
        ("idVendor", ctypes.c_ushort),
        ("idProduct", ctypes.c_ushort),
        ("bcdDevice", ctypes.c_ushort),
        ("iManufacturer", ctypes.c_ubyte),
        ("iProduct", ctypes.c_ubyte),
        ("iSerialNumber", ctypes.c_ubyte),
        ("bNumConfigurations", ctypes.c_ubyte),
    ]


class USB_NODE_CONNECTION_INFORMATION_EX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ConnectionIndex", ctypes.c_ulong),
        ("DeviceDescriptor", USB_DEVICE_DESCRIPTOR),
        ("CurrentConfigurationValue", ctypes.c_ubyte),
        ("Speed", ctypes.c_ubyte),
        ("DeviceIsHub", ctypes.c_ubyte),
        ("DeviceAddress", ctypes.c_ushort),
        ("NumberOfOpenPipes", ctypes.c_ulong),
        ("ConnectionStatus", ctypes.c_ulong),
        ("PipeList", ctypes.c_ubyte * 512),
    ]


class USB_NODE_CONNECTION_INFORMATION_EX_V2(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ConnectionIndex", ctypes.c_ulong),
        ("Length", ctypes.c_ulong),
        ("SupportedUsbProtocols", ctypes.c_ulong),
        ("Flags", ctypes.c_ulong),
    ]


class USB_PORT_CONNECTOR_PROPERTIES(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ConnectionIndex", ctypes.c_ulong),
        ("ActualLength", ctypes.c_ulong),
        ("UsbPortProperties", ctypes.c_ulong),
        ("CompanionIndex", ctypes.c_ushort),
        ("CompanionPortNumber", ctypes.c_ushort),
        ("CompanionHubSymbolicLinkName", ctypes.c_wchar * 512),
    ]


class USB_NODE_CONNECTION_NAME(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("ConnectionIndex", ctypes.c_ulong),
        ("ActualLength", ctypes.c_ulong),
        ("NodeName", ctypes.c_wchar * 512),
    ]


class USB_ROOT_HUB_NAME(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("ActualLength", ctypes.c_ulong), ("RootHubName", ctypes.c_wchar * 512)]


class UsbAccessError(Exception):
    pass


def _api():
    if sys.platform != "win32":
        raise UsbAccessError("O mapeamento USB só funciona no Windows.")
    setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ]
    setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return setupapi, kernel32


def _interface_paths(setupapi, guid_text: str) -> list[str]:
    guid = GUID.parse(guid_text)
    info_set = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    paths = []
    try:
        index = 0
        while True:
            data = SP_DEVICE_INTERFACE_DATA()
            data.cbSize = ctypes.sizeof(data)
            if not setupapi.SetupDiEnumDeviceInterfaces(info_set, None, ctypes.byref(guid), index, ctypes.byref(data)):
                break
            index += 1
            required = wintypes.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set, ctypes.byref(data), None, 0, ctypes.byref(required), None
            )
            buffer = ctypes.create_string_buffer(required.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize é 8 em processos de 64 bits e 6 em 32 bits
            ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if setupapi.SetupDiGetDeviceInterfaceDetailW(info_set, ctypes.byref(data), buffer, required, None, None):
                paths.append(ctypes.wstring_at(ctypes.addressof(buffer) + 4))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info_set)
    return paths


class _Handle:
    def __init__(self, kernel32, path: str) -> None:
        self.kernel32 = kernel32
        self.handle = kernel32.CreateFileW(path, GENERIC_WRITE, FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
        if self.handle in (None, wintypes.HANDLE(-1).value):
            raise UsbAccessError(f"Não foi possível abrir {path} (erro {ctypes.get_last_error()})")

    def ioctl(self, code: int, structure: ctypes.Structure) -> bool:
        returned = wintypes.DWORD()
        size = ctypes.sizeof(structure)
        return bool(
            self.kernel32.DeviceIoControl(
                self.handle,
                code,
                ctypes.byref(structure),
                size,
                ctypes.byref(structure),
                size,
                ctypes.byref(returned),
                None,
            )
        )

    def ioctl_buffer(self, code: int, buffer: ctypes.Array) -> bool:
        returned = wintypes.DWORD()
        size = ctypes.sizeof(buffer)
        return bool(
            self.kernel32.DeviceIoControl(self.handle, code, buffer, size, buffer, size, ctypes.byref(returned), None)
        )

    def connector_properties(self, index: int) -> dict | None:
        """IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES em duas etapas: tamanho, depois os dados."""
        header = (ctypes.c_ubyte * 18)()
        struct.pack_into("<I", header, 0, index)
        if not self.ioctl_buffer(IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES, header):
            return None
        actual = struct.unpack_from("<I", header, 4)[0]
        if actual < 18:
            return None
        full = (ctypes.c_ubyte * actual)()
        struct.pack_into("<I", full, 0, index)
        if not self.ioctl_buffer(IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES, full):
            return None
        _, _, properties, companion_index, companion_port = struct.unpack_from("<IIIHH", full, 0)
        raw_name = bytes(full[16:actual])
        name = raw_name.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
        return {
            "properties": properties,
            "companion_index": companion_index,
            "companion_port": companion_port,
            "companion_hub": name,
        }

    def close(self) -> None:
        self.kernel32.CloseHandle(self.handle)

    def __enter__(self) -> _Handle:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def instance_id_from_path(path: str) -> str:
    r"""\\?\pci#ven_8086&dev_06ed&...#3&11583659&0&a0#{guid} -> PCI\VEN_8086&DEV_06ED&...\3&11583659&0&A0"""
    body = path.split("\\")[-1] if path.startswith("\\\\?\\") else path
    parts = body.split("#")
    return "\\".join(parts[:3]).upper() if len(parts) >= 4 else body.upper()


def _port_class(protocols: int) -> int:
    usb110, usb200, usb300 = protocols & 1, protocols & 2, protocols & 4
    if usb300:
        return SUPER_SPEED
    if usb200 and usb110:
        return HIGH_SPEED
    if usb110:
        return FULL_SPEED
    return UNKNOWN_SPEED


def _device_speed(info: USB_NODE_CONNECTION_INFORMATION_EX, flags: int) -> int:
    if info.Speed == 3 and flags & 0x4:
        return SUPER_SPEED_PLUS
    return {0: LOW_SPEED, 1: FULL_SPEED, 2: HIGH_SPEED, 3: SUPER_SPEED}.get(info.Speed, UNKNOWN_SPEED)


def _hub_ports(kernel32, hub_name: str, names: dict[str, str], depth: int = 0) -> list[dict]:
    path = "\\\\.\\" + hub_name
    ports = []
    with _Handle(kernel32, path) as hub:
        node = (ctypes.c_ubyte * 128)()
        returned = wintypes.DWORD()
        if not kernel32.DeviceIoControl(
            hub.handle, IOCTL_USB_GET_NODE_INFORMATION, node, 128, node, 128, ctypes.byref(returned), None
        ):
            raise UsbAccessError(f"Falha ao ler o hub {hub_name}")
        port_count = node[6]  # NodeType (4 bytes) + bDescriptorLength + bDescriptorType + bNumberOfPorts

        for index in range(1, port_count + 1):
            info = USB_NODE_CONNECTION_INFORMATION_EX(ConnectionIndex=index)
            if not hub.ioctl(IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX, info):
                continue
            v2 = USB_NODE_CONNECTION_INFORMATION_EX_V2(
                ConnectionIndex=index,
                Length=ctypes.sizeof(USB_NODE_CONNECTION_INFORMATION_EX_V2),
                SupportedUsbProtocols=7,
            )
            has_v2 = hub.ioctl(IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2, v2)
            connector = hub.connector_properties(index)
            properties = connector["properties"] if connector else 0

            status = CONNECTION_STATUS.get(info.ConnectionStatus, "Unknown")
            port = {
                "index": index,
                "status": status,
                "class": _port_class(v2.SupportedUsbProtocols) if has_v2 else UNKNOWN_SPEED,
                "type_c": bool(properties & 0x8),
                "user_connectable": bool(properties & 0x1) if connector else True,
                "companion_info": {
                    "port": connector["companion_port"] if connector else 0,
                    "hub": connector["companion_hub"] if connector else "",
                    "multiple_companions": bool(properties & 0x4),
                },
                "devices": [],
            }

            if status == "DeviceConnected":
                descriptor = info.DeviceDescriptor
                vid_pid = f"{descriptor.idVendor:04X}:{descriptor.idProduct:04X}"
                device = {
                    "name": names.get(vid_pid) or f"Dispositivo USB {vid_pid}",
                    "vid_pid": vid_pid,
                    "speed": _device_speed(info, v2.Flags if has_v2 else 0),
                    "devices": [],
                }
                if info.DeviceIsHub and depth < 5:
                    name = USB_NODE_CONNECTION_NAME(ConnectionIndex=index)
                    if hub.ioctl(IOCTL_USB_GET_NODE_CONNECTION_NAME, name) and name.NodeName:
                        try:
                            for child in _hub_ports(kernel32, name.NodeName, names, depth + 1):
                                device["devices"].extend(child["devices"])
                        except UsbAccessError as exc:
                            log.debug("Hub externo ignorado: %s", exc)
                port["devices"].append(device)
            elif status not in ("NoDeviceConnected", "Unknown"):
                port["devices"].append({"error": status})
            ports.append(port)
    return ports


GENERIC_NAMES = ("composite", "composto", "dispositivo de entrada usb", "usb input device", "dispositivo usb")


def _usb_device_names() -> dict[str, str]:
    """VID:PID -> nome amigável, a partir do Gerenciador de Dispositivos."""
    names: dict[str, str] = {}
    try:
        import pythoncom  # type: ignore[import-not-found]
        import wmi  # type: ignore[import-not-found]

        # Sem CoUninitialize: a thread pode continuar usando o COM e isso evita
        # avisos ao liberar objetos que ainda existem.
        pythoncom.CoInitialize()
        connection = wmi.WMI()
        # No WQL esta barra invertida não é escapada
        for entity in connection.query(
            "SELECT Name, PNPDeviceID FROM Win32_PnPEntity WHERE PNPDeviceID LIKE 'USB\\VID%'"
        ):
            match = re.match(r"USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", entity.PNPDeviceID or "", re.I)
            if not match or not entity.Name:
                continue
            key = f"{match.group(1).upper()}:{match.group(2).upper()}"
            current = names.get(key)
            generic = any(word in entity.Name.lower() for word in GENERIC_NAMES)
            if current is None or (any(word in current.lower() for word in GENERIC_NAMES) and not generic):
                names[key] = entity.Name
    except Exception as exc:  # noqa: BLE001 - os nomes são só um complemento
        log.debug("Nomes de dispositivos USB indisponíveis: %s", exc)
    return names


def read_controllers() -> list[dict]:
    """Lê todas as controladoras USB PCI com as portas do hub raiz."""
    setupapi, kernel32 = _api()
    names = _usb_device_names()
    controllers = []
    for path in _interface_paths(setupapi, GUID_DEVINTERFACE_USB_HOST_CONTROLLER):
        instance_id = instance_id_from_path(path)
        if not instance_id.startswith("PCI\\"):
            # Controladoras virtuais (Parsec, VMs, UDE) não existem no macOS
            continue
        match = re.match(r"PCI\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})(?:&SUBSYS_([0-9A-F]{8}))?", instance_id)
        try:
            with _Handle(kernel32, path) as controller:
                root = USB_ROOT_HUB_NAME()
                if not controller.ioctl(IOCTL_USB_GET_ROOT_HUB_NAME, root):
                    continue
                hub_name = root.RootHubName
        except UsbAccessError as exc:
            log.warning("Controladora %s ignorada: %s", instance_id, exc)
            continue
        try:
            ports = _hub_ports(kernel32, hub_name, names)
        except UsbAccessError as exc:
            log.warning("Hub %s ignorado: %s", hub_name, exc)
            continue
        controllers.append(
            {
                "name": instance_id,
                "identifiers": {
                    "instance_id": instance_id,
                    "pci_id": [match.group(1).lower(), match.group(2).lower()] if match else None,
                },
                "hub_name": hub_name,
                "class": None,
                "ports": ports,
            }
        )
    return controllers


CONTROLLER_PROPERTIES = (
    "DEVPKEY_Device_FriendlyName",
    "DEVPKEY_Device_BiosDeviceName",
    "DEVPKEY_Device_LocationInfo",
    "DEVPKEY_Device_LocationPaths",
    "DEVPKEY_PciDevice_ProgIf",
    "DEVPKEY_Device_Service",
)

SERVICE_CLASS = {"usbxhci": 0x30, "usbehci": 0x20, "usbohci": 0x10, "usbuhci": 0x00}


def controller_properties(instance_id: str) -> dict:
    """Nome, caminho ACPI, posição PCI e tipo (XHCI, EHCI...) da controladora."""
    result: dict = {}
    try:
        import pythoncom  # type: ignore[import-not-found]
        import wmi  # type: ignore[import-not-found]

        pythoncom.CoInitialize()
        connection = wmi.WMI()
        # Na comparação com "=" o WQL também aceita a barra invertida sem escape
        rows = connection.query(f"SELECT * FROM Win32_PnPEntity WHERE PNPDeviceID = '{instance_id}'")
        if not rows:
            return result
        properties, _ = rows[0].GetDeviceProperties(list(CONTROLLER_PROPERTIES))
        values = {item.KeyName: item.Data for item in properties if getattr(item, "Data", None) is not None}
    except Exception as exc:  # noqa: BLE001
        log.debug("Propriedades da controladora %s indisponíveis: %s", instance_id, exc)
        return result

    result["name"] = values.get("DEVPKEY_Device_FriendlyName")
    acpi = values.get("DEVPKEY_Device_BiosDeviceName")
    if acpi:
        result["acpi_path"] = acpi
    location = re.findall(r"\d+", values.get("DEVPKEY_Device_LocationInfo") or "")
    if len(location) >= 3:
        result["bdf"] = [int(value) for value in location[:3]]
    if values.get("DEVPKEY_Device_LocationPaths"):
        result["location_paths"] = list(values["DEVPKEY_Device_LocationPaths"])
    prog_if = values.get("DEVPKEY_PciDevice_ProgIf")
    service = str(values.get("DEVPKEY_Device_Service") or "").lower()
    if prog_if is not None:
        result["class"] = int(prog_if)
    elif service in SERVICE_CLASS:
        result["class"] = SERVICE_CLASS[service]
    return result
