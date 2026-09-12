// AI backend management for the desktop shell (v0.2) — the parent
// CorpusMind's OllamaManager pattern, ported to Lens with three upgrades:
//
//   1. LM Studio awareness: the engine already speaks its OpenAI-compatible
//      /v1; the shell reports whether anything answers on :1234 so the UI
//      shows both backends in one place.
//   2. One-click silent install (user decision "b"): Ollama's Windows
//      installer is per-user (no admin), macOS goes to ~/Applications
//      (no admin), Linux uses the official tarball into the app-data dir —
//      never a root prompt, never a UAC wall mid-install.
//   3. Machine-specs probe (sysinfo + nvidia-smi best-effort): the Setup
//      screen shows RAM/VRAM-backed fit badges BEFORE a multi-GB model
//      download starts, and the specs are handed to the engine via
//      LENS_MACHINE_SPECS_JSON so /ai/catalog scores against the same data.
//
// Ollama lifecycle: if something already answers on 11434 we never spawn a
// second daemon (the user may have started `ollama serve` themselves — the
// parent's lesson). We only spawn our own instance when the port is silent,
// and we kill ONLY the child we spawned (never a user-started daemon).

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use log::{error, info, warn};
use serde_json::json;
use tauri::{AppHandle, Emitter, State};

pub const OLLAMA_PORT: u16 = 11434;
pub const LMSTUDIO_PORT: u16 = 1234;

pub struct AiBackendManager {
    child: Mutex<Option<Child>>,
    exe: Mutex<Option<PathBuf>>,
}

impl AiBackendManager {
    pub fn new() -> Self {
        Self { child: Mutex::new(None), exe: Mutex::new(None) }
    }
}

// ─── Discovery ────────────────────────────────────────────────────────────

pub fn is_port_open(port: u16) -> bool {
    TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn expand(p: &str) -> PathBuf {
    let s = if cfg!(windows) {
        p.replace("%LOCALAPPDATA%",
                  &std::env::var("LOCALAPPDATA").unwrap_or_default())
            .replace("%ProgramFiles%",
                     &std::env::var("ProgramFiles").unwrap_or_default())
            .replace("%ProgramFiles(x86)%",
                     &std::env::var("ProgramFiles(x86)").unwrap_or_default())
    } else {
        p.to_string()
    };
    PathBuf::from(shellexpand_home(&s))
}

fn shellexpand_home(s: &str) -> String {
    if let Some(rest) = s.strip_prefix("~/") {
        if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
            return PathBuf::from(home).join(rest).to_string_lossy().into_owned();
        }
    }
    s.to_string()
}

pub fn find_ollama() -> Option<PathBuf> {
    let exe_name = if cfg!(windows) { "ollama.exe" } else { "ollama" };

    // 1. Explicit known locations (expanded for Ollama 0.4+ layouts).
    let mut locations: Vec<PathBuf> = Vec::new();
    if cfg!(windows) {
        for raw in [
            "%LOCALAPPDATA%\\Programs\\Ollama\\ollama.exe",
            "%LOCALAPPDATA%\\Ollama\\ollama.exe",
            "%ProgramFiles%\\Ollama\\ollama.exe",
        ] {
            locations.push(expand(raw));
        }
    } else if cfg!(target_os = "macos") {
        for raw in [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama",
            "~/Applications/Ollama.app/Contents/Resources/ollama",
            "/Applications/Ollama.app/Contents/Resources/ollama",
        ] {
            locations.push(expand(raw));
        }
    } else {
        for raw in ["/usr/local/bin/ollama", "/usr/bin/ollama"] {
            locations.push(expand(raw));
        }
    }

    // 2. The runtime dir this app can install into (Linux bundle path).
    if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
        locations.push(PathBuf::from(&home).join(".lens-engine-data/ollama-runtime/bin/ollama"));
    }

    if let Some(found) = locations.into_iter().find(|c| c.is_file()) {
        return Some(found);
    }

    // 3. PATH fallback (`where` on Windows survives the app-launcher's
    //    trimmed PATH better than a direct spawn attempt).
    let which = if cfg!(windows) { "where" } else { "which" };
    if let Ok(out) = Command::new(which).arg(exe_name).output() {
        if out.status.success() {
            let first = String::from_utf8_lossy(&out.stdout)
                .lines()
                .next()
                .unwrap_or("")
                .trim()
                .to_string();
            if !first.is_empty() {
                return Some(PathBuf::from(first));
            }
        }
    }
    None
}

// ─── `ollama serve` lifecycle ─────────────────────────────────────────────

/// Suppress the console window a child would flash on Windows. MUST be a
/// #[cfg]-gated fn (not `if cfg!()` — that is a runtime check, and the
/// windows-only `CommandExt` import would not compile on Linux/macOS).
fn set_no_window(cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    #[cfg(not(windows))]
    let _ = cmd;
}

fn spawn_serve(exe: &PathBuf) -> Result<Child, String> {
    let log_dir = data_dir().join("logs");
    let _ = std::fs::create_dir_all(&log_dir);
    let log_path = log_dir.join("ollama.log");

    let mut cmd = Command::new(exe);
    cmd.arg("serve");
    // Linux tarball installs need this so downloaded models land in one
    // predictable, uninstallable place; system installs ignore it.
    cmd.env("OLLAMA_MODELS", data_dir().join("ollama-models"));

    let out = std::fs::OpenOptions::new().create(true).append(true).open(&log_path);
    let err = std::fs::OpenOptions::new().create(true).append(true).open(&log_path);
    if let (Ok(o), Ok(e)) = (out, err) {
        cmd.stdout(Stdio::from(o)).stderr(Stdio::from(e));
    }
    set_no_window(&mut cmd);
    cmd.spawn().map_err(|e| format!("failed to spawn `ollama serve`: {e}"))
}

fn wait_for_port(port: u16, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if is_port_open(port) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(400));
    }
    false
}

pub fn ensure_serving(
    mgr: &AiBackendManager,
) -> Result<serde_json::Value, String> {
    if is_port_open(OLLAMA_PORT) {
        return Ok(json!({ "action": "already-running", "reachable": true }));
    }
    let exe = find_ollama().ok_or_else(|| {
        "Ollama is not installed. Use Install on the Setup screen.".to_string()
    })?;
    let mut guard = mgr.child.lock().unwrap();
    if !is_port_open(OLLAMA_PORT) {
        info!("starting `ollama serve` from {}", exe.display());
        let child = spawn_serve(&exe)?;
        *mgr.exe.lock().unwrap() = Some(exe);
        *guard = Some(child);
    }
    if wait_for_port(OLLAMA_PORT, Duration::from_secs(20)) {
        Ok(json!({ "action": "started", "reachable": true }))
    } else {
        Err("ollama serve did not open port 11434 within 20s — see logs/ollama.log".into())
    }
}

pub fn shutdown(mgr: &AiBackendManager) {
    if let Some(mut child) = mgr.child.lock().unwrap().take() {
        info!("ai backend exit — killing our `ollama serve` child");
        #[cfg(unix)]
        {
            let _ = Command::new("kill").arg(child.id().to_string()).output();
            std::thread::sleep(Duration::from_millis(300));
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

// ─── One-click silent install (user decision "b") ─────────────────────────

fn emit(app: &AppHandle, stage: &str, message: &str, done: bool, error: Option<&str>) {
    let payload = json!({
        "stage": stage, "message": message, "done": done, "error": error,
    });
    if let Err(e) = app.emit("ai-install://progress", payload) {
        warn!("emit install progress failed: {e}");
    }
}

fn download(url: &str, dest: &PathBuf) -> Result<(), String> {
    // curl ships with Windows 10+ and every desktop Linux/macOS.
    let status = Command::new("curl")
        .args(["-fL", "--retry", "2", "-o"])
        .arg(dest)
        .arg(url)
        .status()
        .map_err(|e| format!("curl unavailable: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("download failed (curl exit {status})"))
    }
}

pub fn install_ollama(app: AppHandle) {
    std::thread::spawn(move || {
        emit(&app, "start", "Preparing Ollama installation…", false, None);
        let runtime_dir = data_dir();
        let _ = std::fs::create_dir_all(&runtime_dir);

        let result: Result<(), String> = (|| {
            if cfg!(windows) {
                emit(&app, "install", "Running the per-user Ollama installer (silent)…", false, None);
                // Preferred: winget (managed updates). Fallback: direct
                // OllamaSetup.exe — per-user, no admin (Ollama docs).
                let winget_ok = Command::new("winget")
                    .args(["install", "-e", "--id", "Ollama.Ollama", "--silent",
                           "--accept-package-agreements", "--accept-source-agreements"])
                    .status()
                    .map(|s| s.success())
                    .unwrap_or(false);
                if !winget_ok {
                    let tmp = runtime_dir.join("OllamaSetup.exe");
                    emit(&app, "download", "Downloading OllamaSetup.exe…", false, None);
                    download("https://ollama.com/download/OllamaSetup.exe", &tmp)?;
                    emit(&app, "install", "Installing silently (per-user, no admin)…", false, None);
                    let mut installer = Command::new(&tmp);
                    installer.args(["/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"]);
                    set_no_window(&mut installer);
                    let status = installer
                        .status()
                        .map_err(|e| format!("installer launch failed: {e}"))?;
                    if !status.success() {
                        return Err(format!("OllamaSetup.exe exited {status}"));
                    }
                    let _ = std::fs::remove_file(&tmp);
                }
                // New installs land in %LOCALAPPDATA%\Programs\Ollama.
                let fresh = find_ollama().ok_or("installer finished but ollama.exe not found")?;
                info!("ollama installed at {}", fresh.display());
                Ok(())
            } else if cfg!(target_os = "macos") {
                let dmg = runtime_dir.join("Ollama.dmg");
                emit(&app, "download", "Downloading Ollama.dmg…", false, None);
                download("https://ollama.com/download/Ollama.dmg", &dmg)?;
                emit(&app, "install", "Copying Ollama.app to ~/Applications…", false, None);
                let _ = Command::new("hdiutil")
                    .args(["attach", "-nobrowse", "-quiet"])
                    .arg(&dmg)
                    .status();
                // ~/Applications needs no admin; /Applications as fallback.
                let mut copied = Command::new("cp")
                    .args(["-R", "/Volumes/Ollama/Ollama.app"])
                    .arg(shellexpand_home("~/Applications/"))
                    .status()
                    .map(|s| s.success())
                    .unwrap_or(false);
                if !copied {
                    copied = Command::new("cp")
                        .args(["-R", "/Volumes/Ollama/Ollama.app", "/Applications/"])
                        .status()
                        .map(|s| s.success())
                        .unwrap_or(false);
                }
                let _ = Command::new("hdiutil").args(["detach", "-quiet", "/Volumes/Ollama"]).status();
                let _ = std::fs::remove_file(&dmg);
                if !copied && find_ollama().is_none() {
                    return Err("could not copy Ollama.app — please install manually from ollama.com".into());
                }
                Ok(())
            } else {
                // Linux: official tarball into the app-data dir — per-user,
                // silent, no sudo (the install.sh script prompts for a
                // password, which a GUI app must never do).
                let arch = if std::env::consts::ARCH == "aarch64" { "arm64" } else { "amd64" };
                let url = format!("https://ollama.com/download/ollama-linux-{arch}.tgz");
                let tgz = runtime_dir.join("ollama-linux.tgz");
                emit(&app, "download", &format!("Downloading ollama-linux-{arch}.tgz…"), false, None);
                download(&url, &tgz)?;
                emit(&app, "install", "Extracting into ~/.lens-engine-data/ollama-runtime…", false, None);
                let rt = runtime_dir.join("ollama-runtime");
                let _ = std::fs::create_dir_all(&rt);
                let status = Command::new("tar")
                    .args(["-xzf"])
                    .arg(&tgz)
                    .arg("-C")
                    .arg(&rt)
                    .status()
                    .map_err(|e| format!("tar unavailable: {e}"))?;
                let _ = std::fs::remove_file(&tgz);
                if !status.success() || !rt.join("bin/ollama").is_file() {
                    return Err("extraction failed".into());
                }
                Ok(())
            }
        })();

        match result {
            Ok(()) => {
                emit(&app, "verify", "Starting Ollama…", false, None);
                // The UI calls ai_backend_start afterwards; report readiness.
                let ok = wait_for_port(OLLAMA_PORT, Duration::from_secs(3));
                emit(&app, "done",
                     if ok { "Ollama installed and running." }
                     else { "Ollama installed. Starting it now…" },
                     true, None);
            }
            Err(e) => {
                error!("ollama install failed: {e}");
                emit(&app, "done", "Installation failed.", true, Some(&e));
            }
        }
    });
}

// ─── Machine specs (fit badges / avoid punishing offloads) ────────────────

pub fn machine_specs() -> serde_json::Value {
    use sysinfo::System;

    let mut sys = System::new_all();
    sys.refresh_all();
    let ram_gb = sys.total_memory() as f64 / 1024.0 / 1024.0 / 1024.0;
    let cpus = sys.cpus();
    let cpu_model = cpus.first().map(|c| c.brand().trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".into());

    let mut gpus: Vec<serde_json::Value> = Vec::new();
    if cfg!(target_os = "macos") {
        // Apple Silicon: unified memory — GPU can address most of RAM.
        gpus.push(json!({
            "name": "Apple GPU (unified memory)",
            "vram_gb": (ram_gb * 0.75 * 10.0).round() / 10.0,
            "unified": true,
        }));
    } else if let Ok(out) = Command::new("nvidia-smi")
        .args(["--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        .output()
    {
        let txt = String::from_utf8_lossy(&out.stdout);
        for line in txt.lines() {
            let parts: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
            if parts.len() >= 2 {
                if let Ok(mb) = parts[1].parse::<f64>() {
                    gpus.push(json!({
                        "name": parts[0],
                        "vram_gb": (mb / 1024.0 * 10.0).round() / 10.0,
                    }));
                }
            }
        }
    }

    let disk_free_gb = sysinfo::Disks::new_with_refreshed_list()
        .list()
        .iter()
        .filter(|d| d.mount_point().to_string_lossy().len() <= 3
            || d.mount_point().to_string_lossy().starts_with('/'))
        .map(|d| d.available_space())
        .max()
        .map(|b| (b as f64 / 1024.0 / 1024.0 / 1024.0 * 10.0).round() / 10.0);

    json!({
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "cpu_cores": cpus.len(),
        "cpu_model": cpu_model,
        "ram_gb": (ram_gb * 10.0).round() / 10.0,
        "gpus": gpus,
        "disk_free_gb": disk_free_gb,
        "source": "shell",
    })
}

fn data_dir() -> PathBuf {
    if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
        return PathBuf::from(home).join(".lens-engine-data");
    }
    PathBuf::from("./data")
}

// ─── Tauri commands ───────────────────────────────────────────────────────

#[tauri::command]
pub fn ai_backend_status(state: State<'_, AiBackendManager>) -> serde_json::Value {
    json!({
        "ollama": {
            "port": OLLAMA_PORT,
            "reachable": is_port_open(OLLAMA_PORT),
            "exe_found": find_ollama().is_some(),
            "we_spawned": state.child.lock().unwrap().is_some(),
        },
        "lmstudio": { "port": LMSTUDIO_PORT, "reachable": is_port_open(LMSTUDIO_PORT) },
        "machine": machine_specs(),
    })
}

#[tauri::command]
pub fn ai_backend_start(state: State<'_, AiBackendManager>) -> Result<serde_json::Value, String> {
    ensure_serving(&state)
}

#[tauri::command]
pub fn ai_backend_restart(state: State<'_, AiBackendManager>) -> Result<serde_json::Value, String> {
    shutdown(&state);
    std::thread::sleep(Duration::from_millis(600));
    ensure_serving(&state)
}

#[tauri::command]
pub fn ai_install_ollama(app: AppHandle) -> serde_json::Value {
    if find_ollama().is_some() {
        return json!({ "started": false, "reason": "Ollama already installed" });
    }
    install_ollama(app);
    json!({ "started": true })
}

#[tauri::command]
pub fn machine_specs_command() -> serde_json::Value {
    machine_specs()
}
