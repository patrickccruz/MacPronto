"""Sessão de mapeamento USB: mescla leituras, escolhe portas e gera o UTBMap.kext.

Portado do USBToolBox (base.py e Scripts/usbdump.py), licença MIT, com ajustes:
- a leitura vem de macpronto.usb.windows, sem o usbdump.exe;
- portas com Bluetooth viram internas;
- portas USB 3 sem par informado pela BIOS viram "USB 3 Tipo A", não internas,
  quando a BIOS não informa par para nenhuma porta da controladora.
"""

from __future__ import annotations

import binascii
import json
import logging
import plistlib
import shutil
import threading
import time
from pathlib import Path

from macpronto import paths

log = logging.getLogger(__name__)

XHCI = 0x30
MAX_PORTS = 15
HIGH_SPEED, SUPER_SPEED = 2, 3

CONNECTOR_TYPES = {
    0: "USB 2 Tipo A",
    3: "USB 3 Tipo A",
    8: "Tipo C (só USB 2)",
    9: "Tipo C (com chave)",
    10: "Tipo C (sem chave)",
    255: "Interna",
    4: "USB 3 Tipo B",
    5: "USB 3 Micro-B",
    6: "USB 3 Micro-AB",
    1: "Mini-AB",
}

SPEED_LABELS = {0: "USB 1.1", 1: "USB 1.1", 2: "USB 2.0", 3: "USB 3.0", 4: "USB 3.1 Gen 2", 9999: "?"}
CONTROLLER_CLASS_LABELS = {0x00: "USB 1.1 (UHCI)", 0x10: "USB 1.1 (OHCI)", 0x20: "USB 2.0 (EHCI)", 0x30: "USB 3 (XHCI)"}


def hexswap(value: int, width: int = 8) -> bytes:
    """Inteiro em hexadecimal little-endian, como o macOS espera nos mapas."""
    text = hex(value)[2:].zfill(width)
    pairs = [text[i : i + 2] for i in range(0, len(text), 2)]
    return binascii.a2b_hex("".join(reversed(pairs)))


class UsbMapSession:
    def __init__(self, scan_id: str, reader=None, properties=None) -> None:
        self.scan_id = scan_id
        self.file = paths.data_dir() / "usb" / f"{scan_id}.json"
        self.controllers: list[dict] = []
        self._lock = threading.Lock()
        self._reader = reader
        self._properties = properties
        if self.file.exists():
            try:
                self.controllers = json.loads(self.file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("Mapa USB salvo ilegível, começando do zero: %s", exc)

    # ------------------------------------------------------------------ leitura

    def refresh(self) -> dict:
        reader = self._reader
        properties = self._properties
        if reader is None or properties is None:
            from macpronto.usb import windows

            reader = reader or windows.read_controllers
            properties = properties or windows.controller_properties

        snapshot = reader()
        with self._lock:
            for controller in snapshot:
                existing = self._find(controller["identifiers"]["instance_id"])
                if existing is None:
                    info = dict(properties(controller["identifiers"]["instance_id"]))
                    controller["display_name"] = info.pop("name", None) or controller["name"]
                    controller["class"] = info.pop("class", XHCI)
                    controller["identifiers"].update(info)
                    for port in controller["ports"]:
                        self._init_port(port)
                    self.controllers.append(controller)
                else:
                    self._merge(existing, controller)
            self._save()
            return self.state()

    def _find(self, instance_id: str) -> dict | None:
        return next((c for c in self.controllers if c["identifiers"]["instance_id"] == instance_id), None)

    @staticmethod
    def _init_port(port: dict) -> None:
        port["current"] = port.pop("devices", [])
        port["seen"] = [_device_summary(d) for d in _flatten(port["current"])]
        port.setdefault("selected", None)
        port.setdefault("type", None)
        port.setdefault("comment", None)

    def _merge(self, existing: dict, fresh: dict) -> None:
        existing["hub_name"] = fresh["hub_name"]
        by_index = {p["index"]: p for p in existing["ports"]}
        for port in fresh["ports"]:
            old = by_index.get(port["index"])
            if old is None:
                self._init_port(port)
                existing["ports"].append(port)
                continue
            for key in ("status", "class", "type_c", "user_connectable", "companion_info"):
                old[key] = port[key]
            old["current"] = port.get("devices", [])
            known = {(d["name"], d.get("vid_pid")) for d in old["seen"]}
            for device in _flatten(old["current"]):
                summary = _device_summary(device)
                if (summary["name"], summary.get("vid_pid")) not in known:
                    old["seen"].append(summary)
                    known.add((summary["name"], summary.get("vid_pid")))
        existing["ports"].sort(key=lambda p: p["index"])

    def reset(self) -> dict:
        with self._lock:
            self.controllers = []
            if self.file.exists():
                self.file.unlink()
        return self.refresh()

    def _save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.controllers, indent=1, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------ escolhas do usuário

    def companion(self, port: dict) -> dict | None:
        info = port.get("companion_info") or {}
        if not info.get("port") or not info.get("hub"):
            return None
        hub = info["hub"].lower()
        controller = next((c for c in self.controllers if (c.get("hub_name") or "").lower() == hub), None)
        if controller is None:
            return None
        return next((p for p in controller["ports"] if p["index"] == info["port"]), None)

    def _controller_has_companions(self, controller: dict) -> bool:
        return any((p.get("companion_info") or {}).get("port") for p in controller["ports"])

    def is_selected(self, port: dict) -> bool:
        if port.get("selected") is not None:
            return bool(port["selected"])
        companion = self.companion(port)
        return bool(port["seen"]) or bool(companion and companion["seen"])

    def guessed_type(self, controller: dict, port: dict) -> int:
        companion = self.companion(port)
        if any("bluetooth" in d["name"].lower() for d in port["seen"]):
            return 255
        if port.get("type_c") or (companion and companion.get("type_c")):
            return 9
        if not port.get("user_connectable", True):
            return 255
        if companion and {port["class"], companion["class"]} == {HIGH_SPEED, SUPER_SPEED}:
            return 3
        if port["class"] == SUPER_SPEED:
            return 255 if self._controller_has_companions(controller) else 3
        return 0

    def connector_type(self, controller: dict, port: dict) -> int:
        return port["type"] if port.get("type") is not None else self.guessed_type(controller, port)

    def update_port(self, instance_id: str, index: int, changes: dict) -> dict:
        with self._lock:
            controller = self._find(instance_id)
            if controller is None:
                raise ValueError("Controladora não encontrada.")
            port = next((p for p in controller["ports"] if p["index"] == index), None)
            if port is None:
                raise ValueError("Porta não encontrada.")
            companion = self.companion(port)
            if "selected" in changes:
                port["selected"] = bool(changes["selected"])
                if companion is not None:
                    companion["selected"] = bool(changes["selected"])
            if "type" in changes:
                value = changes["type"]
                port["type"] = None if value in (None, "") else int(value)
                if companion is not None:
                    companion["type"] = port["type"]
            if "comment" in changes:
                port["comment"] = (changes["comment"] or "").strip() or None
            self._save()
            return self.state()

    def select(self, mode: str) -> dict:
        """mode: 'used' (só as usadas), 'all' ou 'none'."""
        with self._lock:
            for controller in self.controllers:
                for port in controller["ports"]:
                    if mode == "used":
                        port["selected"] = None
                    else:
                        port["selected"] = mode == "all"
            self._save()
            return self.state()

    # ------------------------------------------------------------------ estado e validação

    def _port_names(self, controller: dict) -> dict[int, str]:
        names: dict[int, str] = {}
        counters: dict[str, int] = {}
        for port in controller["ports"]:
            if controller.get("class") == XHCI and port["class"] == SUPER_SPEED:
                prefix = "SS"
            elif controller.get("class") == XHCI and port["class"] == HIGH_SPEED:
                prefix = "HS"
            else:
                prefix = "PRT"
            counters[prefix] = counters.get(prefix, 0) + 1
            names[port["index"]] = prefix + str(counters[prefix]).zfill(4 - len(prefix))
        return names

    def validate(self) -> list[str]:
        errors = []
        if not any(self.is_selected(p) for c in self.controllers for p in c["ports"]):
            errors.append("Nenhuma porta selecionada. Conecte dispositivos nas portas ou selecione-as manualmente.")
        for controller in self.controllers:
            count = sum(1 for p in controller["ports"] if self.is_selected(p))
            if controller.get("class") == XHCI and count > MAX_PORTS:
                errors.append(
                    f"{controller.get('display_name', controller['name'])}: {count} portas selecionadas. "
                    f"O macOS aceita no máximo {MAX_PORTS} por controladora."
                )
        return errors

    def state(self) -> dict:
        controllers = []
        for controller in self.controllers:
            names = self._port_names(controller)
            ports = []
            for port in controller["ports"]:
                companion = self.companion(port)
                companion_name = None
                if companion is not None:
                    owner = next((c for c in self.controllers if companion in c["ports"]), None)
                    if owner is not None:
                        companion_name = self._port_names(owner).get(companion["index"])
                connector = self.connector_type(controller, port)
                ports.append(
                    {
                        "index": port["index"],
                        "name": names[port["index"]],
                        "speed": SPEED_LABELS.get(port["class"], "?"),
                        "class": port["class"],
                        "selected": self.is_selected(port),
                        "auto_selected": port.get("selected") is None,
                        "type": connector,
                        "type_label": CONNECTOR_TYPES.get(connector, str(connector)),
                        "type_guessed": port.get("type") is None,
                        "comment": port.get("comment"),
                        "current": [_device_summary(d) for d in _flatten(port.get("current", []))],
                        "errors": [
                            d["error"] for d in port.get("current", []) if isinstance(d, dict) and d.get("error")
                        ],
                        "seen": port["seen"],
                        "companion": companion_name,
                        "user_connectable": port.get("user_connectable", True),
                    }
                )
            selected = sum(1 for p in ports if p["selected"])
            controllers.append(
                {
                    "id": controller["identifiers"]["instance_id"],
                    "name": controller.get("display_name") or controller["name"],
                    "class_label": CONTROLLER_CLASS_LABELS.get(controller.get("class"), "?"),
                    "acpi_path": controller["identifiers"].get("acpi_path"),
                    "selected": selected,
                    "total": len(ports),
                    "limit": MAX_PORTS if controller.get("class") == XHCI else None,
                    "ports": ports,
                }
            )
        return {
            "controllers": controllers,
            "errors": self.validate(),
            "connector_types": [{"value": k, "label": v} for k, v in CONNECTOR_TYPES.items()],
            "updated_at": time.strftime("%H:%M:%S"),
        }

    # ------------------------------------------------------------------ geração do kext

    def _unique(self, key, predicate, controller: dict) -> bool:
        if not predicate(controller):
            return False
        values = [key(c) for c in self.controllers if predicate(c)]
        return values.count(key(controller)) == 1

    def _matching_key(self, controller: dict) -> dict:
        identifiers = controller["identifiers"]
        has_acpi = lambda c: bool(c["identifiers"].get("acpi_path"))  # noqa: E731
        acpi_name = lambda c: c["identifiers"]["acpi_path"].rpartition(".")[2]  # noqa: E731
        if self._unique(acpi_name, has_acpi, controller):
            return {"IONameMatch": acpi_name(controller)}
        if identifiers.get("bdf"):
            return {"IOPropertyMatch": {"pcidebug": ":".join(str(i) for i in identifiers["bdf"])}}
        pci_id = identifiers.get("pci_id")
        if pci_id:
            return {"IOPCIPrimaryMatch": f"0x{pci_id[1]}{pci_id[0]}"}
        raise ValueError(f"Não há como identificar a controladora {controller['name']} no macOS.")

    def _personality_name(self, controller: dict) -> str:
        identifiers = controller["identifiers"]
        if identifiers.get("acpi_path"):
            short = identifiers["acpi_path"].rpartition(".")[2]
            has_acpi = lambda c: bool(c["identifiers"].get("acpi_path"))  # noqa: E731
            if self._unique(lambda c: c["identifiers"]["acpi_path"].rpartition(".")[2], has_acpi, controller):
                return short
            return identifiers["acpi_path"].lstrip("\\")
        if identifiers.get("bdf"):
            return ":".join(str(i) for i in identifiers["bdf"])
        return controller["name"]

    def build_kext(self, destination: Path) -> Path:
        errors = self.validate()
        if errors:
            raise ValueError(" ".join(errors))

        template_file = paths.third_party_dir() / "USBToolBox" / "resources" / "Info.plist"
        with template_file.open("rb") as handle:
            template = plistlib.load(handle)

        for controller in self.controllers:
            selected = [p for p in controller["ports"] if self.is_selected(p)]
            if not selected:
                continue  # controladoras sem portas escolhidas ficam fora do mapa
            names = self._port_names(controller)
            personality = {
                "CFBundleIdentifier": "com.dhinakg.USBToolBox.kext",
                "IOClass": "USBToolBox",
                "IOProviderClass": "IOPCIDevice",
                "IOMatchCategory": "USBToolBox",
                **self._matching_key(controller),
                "IOProviderMergeProperties": {"ports": {}, "port-count": None},
            }
            highest = 0
            for port in selected:
                highest = max(highest, port["index"])
                entry = {"port": hexswap(port["index"]), "UsbConnector": self.connector_type(controller, port)}
                if port.get("comment"):
                    entry["#comment"] = port["comment"]
                personality["IOProviderMergeProperties"]["ports"][names[port["index"]]] = entry
            personality["IOProviderMergeProperties"]["port-count"] = hexswap(highest)
            template["IOKitPersonalities"][self._personality_name(controller)] = personality

        template["OSBundleLibraries"] = {"com.dhinakg.USBToolBox.kext": "1.0.0"}

        kext = destination / "UTBMap.kext"
        if kext.exists():
            shutil.rmtree(kext)
        (kext / "Contents").mkdir(parents=True)
        with (kext / "Contents" / "Info.plist").open("wb") as handle:
            plistlib.dump(template, handle, sort_keys=True)
        log.info("UTBMap.kext gerado em %s", kext)
        return kext


def _flatten(devices: list) -> list[dict]:
    flat = []
    for device in devices or []:
        if not isinstance(device, dict) or device.get("error"):
            continue
        flat.append(device)
        flat.extend(_flatten(device.get("devices", [])))
    return flat


def _device_summary(device: dict) -> dict:
    return {
        "name": (device.get("name") or "Dispositivo USB").strip(),
        "vid_pid": device.get("vid_pid"),
        "speed": SPEED_LABELS.get(device.get("speed", 9999), "?"),
    }
