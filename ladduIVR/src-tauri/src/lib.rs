use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::thread;
use std::time::Duration;

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ConnectedDevice {
    pub mac: String,
    pub name: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct BluetoothInfo {
    pub powered: bool,
    pub class: String,
    pub class_hex: String,
    pub has_handsfree_uuid: bool,
    pub controller_name: String,
    pub connected_devices: Vec<ConnectedDevice>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SystemStatus {
    pub mode: String, // "handsfree" or "normal"
    pub info: BluetoothInfo,
    pub roles_file_exists: bool,
}

fn get_wireplumber_paths() -> (PathBuf, PathBuf) {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    let dir = PathBuf::from(home)
        .join(".config")
        .join("wireplumber")
        .join("wireplumber.conf.d");
    let file = dir.join("51-bluetooth-roles.conf");
    (dir, file)
}

fn run_cmd(cmd: &str) -> (bool, String) {
    match Command::new("sh").arg("-c").arg(cmd).output() {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let out = if !stdout.is_empty() { stdout } else { stderr };
            (output.status.success(), out.trim().to_string())
        }
        Err(e) => (false, e.to_string()),
    }
}

fn fetch_bluetooth_info() -> BluetoothInfo {
    let (ok, out) = run_cmd("bluetoothctl show");
    let lower_out = out.to_lowercase();
    let powered = lower_out.contains("powered: yes");
    let has_hf_uuid = lower_out.contains("0000111e") || lower_out.contains("handsfree");

    let mut class_hex = String::from("0x000000");
    let mut class_desc = String::from("Unknown");
    let mut controller_name = String::from("Default Adapter");

    // Extract Class
    for line in out.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("Class:") {
            if let Some(val) = trimmed.strip_prefix("Class:") {
                let hex = val.trim().to_lowercase();
                class_hex = hex.clone();
                if hex.contains("006c010c") || hex.contains("6c010c") {
                    class_desc = "Telephony + Audio (Hands-Free Device)".to_string();
                } else if hex.contains("000c010c") || hex.contains("c010c") {
                    class_desc = "Computer / Laptop (Standard)".to_string();
                } else {
                    class_desc = format!("Custom ({})", hex);
                }
            }
        } else if trimmed.starts_with("Name:") {
            if let Some(val) = trimmed.strip_prefix("Name:") {
                controller_name = val.trim().to_string();
            }
        }
    }

    // Extract connected devices
    let mut connected_devices = Vec::new();
    let (dev_ok, dev_out) = run_cmd("bluetoothctl devices Connected");
    if dev_ok && !dev_out.is_empty() {
        for line in dev_out.lines() {
            let line = line.trim();
            if line.starts_with("Device ") {
                let parts: Vec<&str> = line.splitn(3, ' ').collect();
                if parts.len() >= 2 {
                    let mac = parts[1].to_string();
                    let name = if parts.len() >= 3 {
                        parts[2].to_string()
                    } else {
                        mac.clone()
                    };
                    connected_devices.push(ConnectedDevice { mac, name });
                }
            }
        }
    }

    BluetoothInfo {
        powered: if ok { powered } else { false },
        class: class_desc,
        class_hex,
        has_handsfree_uuid: has_hf_uuid,
        controller_name,
        connected_devices,
    }
}

fn determine_current_mode(info: &BluetoothInfo) -> String {
    let (_, file_path) = get_wireplumber_paths();
    if file_path.exists() {
        if let Ok(content) = fs::read_to_string(&file_path) {
            if content.contains("hfp_hf") {
                return "handsfree".to_string();
            } else if content.contains("a2dp_sink") && !content.contains("hfp_hf") {
                return "normal".to_string();
            }
        }
    }

    if info.has_handsfree_uuid || info.class_hex.contains("6c010c") {
        "handsfree".to_string()
    } else {
        "normal".to_string()
    }
}

fn restart_audio() {
    let _ = run_cmd("systemctl --user daemon-reload");
    let _ = run_cmd("systemctl --user restart pipewire wireplumber");
    thread::sleep(Duration::from_millis(1500));
}

const HANDSFREE_CONFIG: &str = r#"monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source bap_sink bap_source hsp_hs hsp_ag hfp_hf hfp_ag ]
  bluez5.hfphsp-backend = "native"
}
"#;

const NORMAL_CONFIG: &str = r#"monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source ]
}
"#;

#[tauri::command]
fn get_status() -> Result<SystemStatus, String> {
    let info = fetch_bluetooth_info();
    let mode = determine_current_mode(&info);
    let (_, file_path) = get_wireplumber_paths();

    Ok(SystemStatus {
        mode,
        info,
        roles_file_exists: file_path.exists(),
    })
}

#[tauri::command]
fn switch_mode(target_mode: String) -> Result<SystemStatus, String> {
    let (dir_path, file_path) = get_wireplumber_paths();
    if let Err(e) = fs::create_dir_all(&dir_path) {
        return Err(format!("Failed to create config directory: {}", e));
    }

    let config_content = match target_mode.as_str() {
        "handsfree" => HANDSFREE_CONFIG,
        "normal" => NORMAL_CONFIG,
        other => return Err(format!("Unknown mode requested: {}", other)),
    };

    if let Err(e) = fs::write(&file_path, config_content) {
        return Err(format!("Failed to write configuration: {}", e));
    }

    restart_audio();

    let info = fetch_bluetooth_info();
    let mode = determine_current_mode(&info);

    Ok(SystemStatus {
        mode,
        info,
        roles_file_exists: file_path.exists(),
    })
}

#[tauri::command]
fn toggle_mode() -> Result<SystemStatus, String> {
    let current_info = fetch_bluetooth_info();
    let current_mode = determine_current_mode(&current_info);
    let target = if current_mode == "handsfree" {
        "normal"
    } else {
        "handsfree"
    };

    switch_mode(target.to_string())
}

#[tauri::command]
fn restart_audio_stack() -> Result<String, String> {
    restart_audio();
    Ok("Audio services (PipeWire / WirePlumber) restarted successfully".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            get_status,
            switch_mode,
            toggle_mode,
            restart_audio_stack
        ])
        .run(tauri::generate_context!())
        .expect("error while building tauri application");
}
