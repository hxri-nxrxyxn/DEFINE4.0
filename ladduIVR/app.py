#!/usr/bin/env python3
"""
Bluetooth Hands-Free / Normal Laptop Mode Manager with UI
Allows toggling between:
  - Hands-Free Mode (HFP bidirectional call routing to/from phone)
  - Normal Laptop Mode (Standard computer audio)

Supports:
  - Native GTK 3 Desktop GUI (default in desktop session)
  - Web UI (run with --web, or automatic fallback in headless environments)
"""

import os
import sys
import threading
import time
from bt_controller import (
    get_bluetooth_info,
    get_current_mode,
    set_handsfree_mode,
    set_normal_mode,
    toggle_mode
)

def build_gtk_app():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib

    css_data = b"""
    window {
        background-color: #0f141c;
    }
    .main-box {
        padding: 24px;
    }
    .title-label {
        color: #ffffff;
        font-size: 18px;
        font-weight: bold;
    }
    .subtitle-label {
        color: #8b9bb4;
        font-size: 12px;
        margin-bottom: 12px;
    }
    .card {
        background-color: #1a2230;
        border: 1px solid #2a364a;
        border-radius: 12px;
        padding: 18px;
    }
    .mode-badge-handsfree {
        background-color: #238636;
        color: #ffffff;
        font-size: 15px;
        font-weight: bold;
        border-radius: 8px;
        padding: 8px 16px;
    }
    .mode-badge-normal {
        background-color: #1f6feb;
        color: #ffffff;
        font-size: 15px;
        font-weight: bold;
        border-radius: 8px;
        padding: 8px 16px;
    }
    .desc-label {
        color: #c9d1d9;
        font-size: 12px;
    }
    .info-label {
        color: #8b9bb4;
        font-size: 11px;
    }
    .info-val {
        color: #58a6ff;
        font-size: 11px;
        font-weight: bold;
    }
    .btn-toggle-to-hf {
        background: #238636;
        color: #ffffff;
        font-size: 14px;
        font-weight: bold;
        border-radius: 10px;
        padding: 12px 20px;
        border: none;
    }
    .btn-toggle-to-hf:hover {
        background: #2ea043;
    }
    .btn-toggle-to-norm {
        background: #1f6feb;
        color: #ffffff;
        font-size: 14px;
        font-weight: bold;
        border-radius: 10px;
        padding: 12px 20px;
        border: none;
    }
    .btn-toggle-to-norm:hover {
        background: #388bfd;
    }
    .log-box {
        background-color: #111722;
        border: 1px solid #2a364a;
        border-radius: 8px;
        padding: 8px;
        font-family: monospace;
        font-size: 11px;
        color: #8b949e;
    }
    """

    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(css_data)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    class BluetoothModeWindow(Gtk.Window):
        def __init__(self):
            super().__init__(title="Bluetooth Audio Mode Manager")
            self.set_default_size(480, 520)
            self.set_position(Gtk.WindowPosition.CENTER)
            self.connect("destroy", Gtk.main_quit)

            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            main_box.get_style_context().add_class("main-box")
            self.add(main_box)

            # Header
            header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            title = Gtk.Label(label="📱 Bluetooth Audio Mode Manager")
            title.get_style_context().add_class("title-label")
            title.set_xalign(0)
            subtitle = Gtk.Label(label="Toggle between Normal Laptop Mode and Hands-Free Call Mode")
            subtitle.get_style_context().add_class("subtitle-label")
            subtitle.set_xalign(0)
            header_box.pack_start(title, False, False, 0)
            header_box.pack_start(subtitle, False, False, 0)
            main_box.pack_start(header_box, False, False, 0)

            # Mode Status Card
            self.status_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            self.status_card.get_style_context().add_class("card")

            status_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            status_title = Gtk.Label(label="CURRENT MODE:")
            status_title.get_style_context().add_class("info-label")
            self.mode_badge = Gtk.Label(label="Checking...")
            status_header.pack_start(status_title, False, False, 0)
            status_header.pack_end(self.mode_badge, False, False, 0)
            self.status_card.pack_start(status_header, False, False, 0)

            self.desc_label = Gtk.Label(label="Detecting configuration...")
            self.desc_label.get_style_context().add_class("desc-label")
            self.desc_label.set_line_wrap(True)
            self.desc_label.set_xalign(0)
            self.status_card.pack_start(self.desc_label, False, False, 0)

            main_box.pack_start(self.status_card, False, False, 0)

            # Info Card
            info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            info_card.get_style_context().add_class("card")

            self.class_label = Gtk.Label(label="Bluetooth Class: ...")
            self.class_label.get_style_context().add_class("info-label")
            self.class_label.set_xalign(0)
            info_card.pack_start(self.class_label, False, False, 0)

            self.dev_label = Gtk.Label(label="Connected Phone: None")
            self.dev_label.get_style_context().add_class("info-label")
            self.dev_label.set_xalign(0)
            info_card.pack_start(self.dev_label, False, False, 0)

            main_box.pack_start(info_card, False, False, 0)

            # Toggle Button
            self.toggle_btn = Gtk.Button(label="Loading...")
            self.toggle_btn.connect("clicked", self.on_toggle_clicked)
            main_box.pack_start(self.toggle_btn, False, False, 0)

            # Log Area
            log_title = Gtk.Label(label="ACTIVITY LOG:")
            log_title.get_style_context().add_class("info-label")
            log_title.set_xalign(0)
            main_box.pack_start(log_title, False, False, 0)

            self.log_scroller = Gtk.ScrolledWindow()
            self.log_scroller.set_min_content_height(100)
            self.log_view = Gtk.TextView()
            self.log_view.set_editable(False)
            self.log_view.get_style_context().add_class("log-box")
            self.log_scroller.add(self.log_view)
            main_box.pack_start(self.log_scroller, True, True, 0)

            self.log_buffer = self.log_view.get_buffer()
            self.append_log("Application initialized.")

            # Periodic status check
            GLib.timeout_add_seconds(3, self.periodic_check)
            self.update_ui_state()

        def append_log(self, text):
            now = time.strftime("%H:%M:%S")
            line = f"[{now}] {text}\n"
            end_iter = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end_iter, line)

        def periodic_check(self):
            self.update_ui_state()
            return True

        def update_ui_state(self):
            mode = get_current_mode()
            info = get_bluetooth_info()

            ctx = self.mode_badge.get_style_context()
            btn_ctx = self.toggle_btn.get_style_context()

            ctx.remove_class("mode-badge-handsfree")
            ctx.remove_class("mode-badge-normal")
            btn_ctx.remove_class("btn-toggle-to-hf")
            btn_ctx.remove_class("btn-toggle-to-norm")

            if mode == "handsfree":
                self.mode_badge.set_text("📞 HANDS-FREE MODE (Active)")
                ctx.add_class("mode-badge-handsfree")
                self.desc_label.set_text("Phone calls route bidirectionally (mic & speaker) between your phone and this laptop.")
                self.toggle_btn.set_label("⇄ Switch to Normal Laptop Mode")
                btn_ctx.add_class("btn-toggle-to-norm")
            else:
                self.mode_badge.set_text("💻 NORMAL LAPTOP MODE (Active)")
                ctx.add_class("mode-badge-normal")
                self.desc_label.set_text("Standard laptop Bluetooth audio. Phone calls stay on your phone and will NOT hijack laptop audio.")
                self.toggle_btn.set_label("⇄ Switch to Hands-Free Mode")
                btn_ctx.add_class("btn-toggle-to-hf")

            self.class_label.set_text(f"Bluetooth Device Class: {info['class']} ({info['class_hex']})")
            if info["connected_devices"]:
                dev_str = ", ".join([d["name"] for d in info["connected_devices"]])
                self.dev_label.set_text(f"Connected Device(s): {dev_str}")
            else:
                self.dev_label.set_text("Connected Device(s): None (Connect phone via Bluetooth)")

        def on_toggle_clicked(self, widget):
            self.toggle_btn.set_sensitive(False)
            self.toggle_btn.set_label("Switching mode, please wait...")
            self.append_log("Switching Bluetooth mode and restarting audio stack...")

            def worker():
                new_mode = toggle_mode()
                GLib.idle_add(self.on_toggle_finished, new_mode)

            threading.Thread(target=worker, daemon=True).start()

        def on_toggle_finished(self, new_mode):
            self.toggle_btn.set_sensitive(True)
            self.update_ui_state()
            self.append_log(f"Switched to: {new_mode.upper()} MODE successfully.")

    win = BluetoothModeWindow()
    win.show_all()
    Gtk.main()

def run_web_server(port=5050):
    import http.server
    import json
    import socketserver
    import urllib.parse
    import webbrowser

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bluetooth Audio Mode Manager</title>
  <style>
    :root {
      --bg: #0f141c;
      --card-bg: #1a2230;
      --border: #2a364a;
      --text: #e6edf3;
      --text-muted: #8b9bb4;
      --green: #238636;
      --green-hover: #2ea043;
      --blue: #1f6feb;
      --blue-hover: #388bfd;
      --code-bg: #111722;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 32px 16px; }
    .container { width: 100%; max-width: 520px; display: flex; flex-direction: column; gap: 20px; }
    .header { text-align: center; }
    .header h1 { font-size: 1.8rem; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 10px; }
    .header p { color: var(--text-muted); font-size: 0.9rem; margin-top: 4px; }
    .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 24px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
    .mode-badge { padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 1rem; display: inline-block; margin-bottom: 12px; }
    .mode-badge.handsfree { background: var(--green); color: #fff; }
    .mode-badge.normal { background: var(--blue); color: #fff; }
    .desc { font-size: 0.9rem; color: #c9d1d9; line-height: 1.5; margin-bottom: 20px; }
    .meta-row { display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--text-muted); margin-bottom: 8px; }
    .meta-val { color: #58a6ff; font-weight: 600; }
    .toggle-btn { width: 100%; padding: 16px; border-radius: 12px; font-size: 1.1rem; font-weight: 700; cursor: pointer; border: none; transition: all 0.2s; margin-top: 10px; color: #fff; }
    .toggle-btn.btn-to-norm { background: var(--blue); }
    .toggle-btn.btn-to-norm:hover { background: var(--blue-hover); }
    .toggle-btn.btn-to-hf { background: var(--green); }
    .toggle-btn.btn-to-hf:hover { background: var(--green-hover); }
    .toggle-btn:disabled { opacity: 0.5; cursor: wait; }
    .logs-card { margin-top: 10px; }
    .log-box { background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px; height: 120px; overflow-y: auto; font-family: monospace; font-size: 0.8rem; color: #8b949e; }
    .log-line { margin-bottom: 4px; }
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <h1><span>📱</span> Bluetooth Mode Manager</h1>
      <p>Toggle between Normal Laptop Mode and Hands-Free Call Mode</p>
    </header>

    <div class="card">
      <div id="modeBadge" class="mode-badge normal">Checking...</div>
      <p id="modeDesc" class="desc">Loading current mode configuration...</p>
      
      <div class="meta-row">
        <span>Bluetooth Class:</span>
        <span id="classVal" class="meta-val">...</span>
      </div>
      <div class="meta-row">
        <span>Connected Devices:</span>
        <span id="devicesVal" class="meta-val">...</span>
      </div>

      <button id="toggleBtn" class="toggle-btn btn-to-hf">Switch Mode</button>
    </div>

    <div class="card logs-card">
      <h3 style="font-size:0.85rem; color:var(--text-muted); margin-bottom:8px; text-transform:uppercase;">Activity Log</h3>
      <div id="logBox" class="log-box">
        <div class="log-line">[System] Web UI connected.</div>
      </div>
    </div>
  </div>

  <script>
    const modeBadge = document.getElementById('modeBadge');
    const modeDesc = document.getElementById('modeDesc');
    const classVal = document.getElementById('classVal');
    const devicesVal = document.getElementById('devicesVal');
    const toggleBtn = document.getElementById('toggleBtn');
    const logBox = document.getElementById('logBox');

    function addLog(msg) {
      const line = document.createElement('div');
      line.className = 'log-line';
      line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
      logBox.prepend(line);
    }

    async function loadStatus() {
      try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        
        if (data.mode === 'handsfree') {
          modeBadge.textContent = '📞 HANDS-FREE MODE (Active)';
          modeBadge.className = 'mode-badge handsfree';
          modeDesc.textContent = 'Phone calls route bidirectionally (mic & speaker) between your phone and this laptop.';
          toggleBtn.textContent = '⇄ Switch to Normal Laptop Mode';
          toggleBtn.className = 'toggle-btn btn-to-norm';
        } else {
          modeBadge.textContent = '💻 NORMAL LAPTOP MODE (Active)';
          modeBadge.className = 'mode-badge normal';
          modeDesc.textContent = 'Standard laptop Bluetooth audio. Phone calls stay on your phone and will NOT hijack laptop audio.';
          toggleBtn.textContent = '⇄ Switch to Hands-Free Mode';
          toggleBtn.className = 'toggle-btn btn-to-hf';
        }

        classVal.textContent = `${data.info.class} (${data.info.class_hex})`;
        if (data.info.connected_devices && data.info.connected_devices.length > 0) {
          devicesVal.textContent = data.info.connected_devices.map(d => d.name).join(', ');
        } else {
          devicesVal.textContent = 'None';
        }
      } catch (err) {
        modeBadge.textContent = 'Error connecting to backend';
      }
    }

    toggleBtn.addEventListener('click', async () => {
      toggleBtn.disabled = true;
      toggleBtn.textContent = 'Switching mode...';
      addLog('Toggling Bluetooth audio mode and restarting audio stack...');
      try {
        const resp = await fetch('/api/toggle', { method: 'POST' });
        const data = await resp.json();
        addLog(`Switched to: ${data.mode.toUpperCase()} MODE.`);
      } catch (err) {
        addLog(`Error: ${err.message}`);
      } finally {
        toggleBtn.disabled = false;
        await loadStatus();
      }
    });

    loadStatus();
    setInterval(loadStatus, 3000);
  </script>
</body>
</html>
"""

    class WebHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/status":
                mode = get_current_mode()
                info = get_bluetooth_info()
                resp = {"mode": mode, "info": info}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))

        def do_POST(self):
            if self.path == "/api/toggle":
                new_mode = toggle_mode()
                info = get_bluetooth_info()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"mode": new_mode, "info": info}).encode("utf-8"))
            else:
                self.send_error(404)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    print(f"==================================================")
    print(f"  Bluetooth Mode Manager (Web UI)")
    print(f"  Open in browser: http://localhost:{port}")
    print(f"==================================================")
    if os.environ.get("DISPLAY"):
        threading.Thread(target=lambda: (time.sleep(1), webbrowser.open(f"http://localhost:{port}")), daemon=True).start()

    with socketserver.ThreadingTCPServer(("", port), WebHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")

def main():
    use_web = "--web" in sys.argv or not os.environ.get("DISPLAY")
    if not use_web:
        try:
            build_gtk_app()
            return
        except Exception as e:
            print(f"Could not initialize GTK UI ({e}), falling back to Web UI...")
            use_web = True

    if use_web:
        port = 5050
        for arg in sys.argv:
            if arg.startswith("--port="):
                port = int(arg.split("=")[1])
        run_web_server(port)

if __name__ == "__main__":
    main()
