#!/usr/bin/env python3
"""
Bluetooth Mode Controller for Linux (Pop!_OS / PipeWire / WirePlumber / BlueZ)
Manages switching between:
  1. Hands-Free Mode: Phone calls route bidirectional audio (mic + speaker) to the laptop.
  2. Normal Laptop Mode: Standard computer Bluetooth, no hands-free telephony hijack.
"""

import os
import re
import subprocess
import time
from pathlib import Path

WIREPLUMBER_CONF_DIR = Path.home() / ".config" / "wireplumber" / "wireplumber.conf.d"
ROLES_CONF_PATH = WIREPLUMBER_CONF_DIR / "51-bluetooth-roles.conf"

HANDSFREE_CONFIG = """monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source hsp_hs hsp_ag hfp_hf hfp_ag ]
  bluez5.hfphsp-backend = "native"
}
"""

NORMAL_CONFIG = """monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source ]
}
"""

def run_command(cmd, timeout=8):
    """Run shell command safely and return (success, stdout)."""
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return res.returncode == 0, res.stdout.strip()
    except Exception as e:
        return False, str(e)

def get_bluetooth_info():
    """Inspect BlueZ controller and connected devices."""
    ok, out = run_command("bluetoothctl show")
    info = {
        "powered": "yes" in out.lower(),
        "class": "Unknown",
        "class_hex": "0x000000",
        "has_handsfree_uuid": "0000111e" in out.lower() or "handsfree" in out.lower(),
        "controller_name": "Unknown",
        "connected_devices": []
    }
    
    # Extract Class
    m_class = re.search(r"Class:\s+(0x[0-9a-fA-F]+)", out)
    if m_class:
        info["class_hex"] = m_class.group(1).lower()
        if "006c010c" in info["class_hex"]:
            info["class"] = "Telephony + Audio (Hands-Free Device)"
        elif "000c010c" in info["class_hex"]:
            info["class"] = "Computer / Laptop (Standard)"
        else:
            info["class"] = f"Custom ({info['class_hex']})"

    # Extract Controller Name
    m_name = re.search(r"Name:\s+(.+)", out)
    if m_name:
        info["controller_name"] = m_name.group(1).strip()

    # Get Connected Devices
    ok_dev, out_dev = run_command("bluetoothctl devices Connected")
    if ok_dev and out_dev:
        for line in out_dev.splitlines():
            line = line.strip()
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                mac = parts[1] if len(parts) > 1 else ""
                name = parts[2] if len(parts) > 2 else mac
                info["connected_devices"].append({"mac": mac, "name": name})

    return info

def get_current_mode():
    """
    Determine whether currently in Hands-Free or Normal mode.
    Returns: 'handsfree' or 'normal'
    """
    if ROLES_CONF_PATH.exists():
        try:
            content = ROLES_CONF_PATH.read_text()
            if "hfp_hf" in content:
                return "handsfree"
        except Exception:
            pass

    bt_info = get_bluetooth_info()
    if bt_info["has_handsfree_uuid"] or "6c010c" in bt_info["class_hex"]:
        return "handsfree"

    return "normal"

def restart_audio_stack():
    """Restart PipeWire and WirePlumber to apply role changes."""
    run_command("systemctl --user daemon-reload")
    run_command("systemctl --user restart pipewire wireplumber")
    time.sleep(1.5)

def set_handsfree_mode():
    """
    Switch to Hands-Free Mode:
    Enables bidirectional HFP telephony routing so phone calls route to laptop.
    """
    WIREPLUMBER_CONF_DIR.mkdir(parents=True, exist_ok=True)
    ROLES_CONF_PATH.write_text(HANDSFREE_CONFIG)
    restart_audio_stack()
    return get_current_mode() == "handsfree"

def set_normal_mode():
    """
    Switch to Normal Laptop Mode:
    Reverts Bluetooth to standard computer A2DP audio. Phone calls stay on phone.
    """
    WIREPLUMBER_CONF_DIR.mkdir(parents=True, exist_ok=True)
    ROLES_CONF_PATH.write_text(NORMAL_CONFIG)
    restart_audio_stack()
    return get_current_mode() == "normal"

def toggle_mode():
    """Toggle between Hands-Free Mode and Normal Laptop Mode."""
    current = get_current_mode()
    if current == "handsfree":
        set_normal_mode()
        return "normal"
    else:
        set_handsfree_mode()
        return "handsfree"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "handsfree":
            set_handsfree_mode()
        elif cmd == "normal":
            set_normal_mode()
        elif cmd == "toggle":
            toggle_mode()
    print("Current Mode:", get_current_mode())
    info = get_bluetooth_info()
    print("Class:", info["class"], f"({info['class_hex']})")
    print("Hands-Free Profile Active:", info["has_handsfree_uuid"])
    print("Connected Devices:", [d['name'] for d in info['connected_devices']])
