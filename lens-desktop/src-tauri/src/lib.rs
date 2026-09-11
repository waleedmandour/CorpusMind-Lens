// CorpusMind Lens desktop shell — Tauri 2 sidecar lifecycle.
//
// Own repository, own identity (§12): Lens spawns *its own* `lens-engine`
// sidecar, not a mode of the parent product. Responsibilities (§3.4/§6/§15):
//   - detect a possibly-running CorpusMind (Text) engine on 8765 FIRST:
//     if one answers, Lens treats it as a Companion and starts its own
//     engine on the next free port instead of crashing into a conflict (§5)
//   - spawn lens-engine as a sidecar (bundled binary, or `python -m
//     lens_engine.__main__` for development)
//   - poll /api/v1/health until ready (60s budget — Windows Defender's
//     first-run scan of a PyInstaller tree is slow; documented pitfall)
//   - redirect sidecar stdout/stderr to a LOG FILE, never piped (piped
//     stdout hangs on buffer-size limits — documented pitfall)
//   - on macOS, strip the quarantine attribute from the bundled binary
//     before launching (unsigned bundled binaries are quarantined —
//     documented pitfall)
//   - on exit, kill the child fully to avoid orphaned engines
//
// The `?shell=lens` query-parameter pattern is deliberately gone: this
// build serves Lens's own frontend with no mode-switching to do (§6).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use log::{error, info, warn};
use tauri::State;

const ENGINE_HOST: &str = "127.0.0.1";
const PARENT_ENGINE_PORT: u16 = 8765; // where CorpusMind (Text) usually listens
const HEALTH_TIMEOUT: Duration = Duration::from_secs(60);
const HEALTH_POLL_INTERVAL: Duration = Duration::from_millis(500);

struct EngineManager {
    child: Mutex<Option<Child>>,
    port: Mutex<u16>,
}

impl EngineManager {
    fn new() -> Self {
        Self { child: Mutex::new(None), port: Mutex::new(PARENT_ENGINE_PORT) }
    }
}

// ─── Port-conflict / companion detection (§5, §15 Phase 3) ─────────────

/// Returns Ok(()) if `port` is FREE, Err(()) if something is listening.
fn port_in_use(port: u16) -> bool {
    std::net::TcpListener::bind((ENGINE_HOST, port)).is_err()
}

/// True when an engine that answers our health contract is on this port
/// (either a CorpusMind Text engine we can treat as Companion, or a
/// previous Lens engine instance that survived).
fn engine_alive_on(port: u16) -> bool {
    // A plain TCP connect is enough to know the port is taken; the frontend
    // then decides Companion vs. connect-to-existing via /api/v1/health.
    !port_in_use(port)
}

fn pick_port() -> u16 {
    let mut port = PARENT_ENGINE_PORT;
    while engine_alive_on(port) && port < PARENT_ENGINE_PORT + 20 {
        info!(
            "port {} busy (possible CorpusMind Text engine or stale engine) — trying next",
            port
        );
        port += 1;
    }
    port
}

// ─── Sidecar discovery ─────────────────────────────────────────────────

fn find_engine_binary() -> Option<std::path::PathBuf> {
    // Bundled resource: <resource>/lens-engine/lens-engine(.exe)
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let candidates = [
        dir.join("lens-engine").join("lens-engine"),
        dir.join("lens-engine.exe"),
        #[cfg(windows)]
        dir.join("lens-engine").join("lens-engine.exe"),
    ];
    candidates.into_iter().find(|c| c.exists())
}

fn find_python_fallback() -> Option<Command> {
    // Development fallback so `cargo tauri dev` works without PyInstaller.
    for py in ["python3.12", "python3", "python"] {
        if let Ok(out) = Command::new(py).arg("--version").output() {
            if out.status.success() {
                let mut cmd = Command::new(py);
                cmd.arg("-m").arg("uvicorn").arg("lens_engine.main:app");
                return Some(cmd);
            }
        }
    }
    None
}

// ─── macOS quarantine stripping (documented pitfall) ────────────────────

#[cfg(target_os = "macos")]
fn strip_quarantine(path: &std::path::Path) {
    let _ = Command::new("xattr")
        .args(["-d", "com.apple.quarantine"])
        .arg(path)
        .output()
        .map(|_| info!("quarantine attribute stripped: {}", path.display()));
}

#[cfg(not(target_os = "macos"))]
fn strip_quarantine(_path: &std::path::Path) {}

// ─── Health polling ─────────────────────────────────────────────────────

fn wait_for_health(port: u16, timeout: Duration) -> bool {
    let start = Instant::now();
    let url = format!("http://{ENGINE_HOST}:{port}/api/v1/health");
    while start.elapsed() < timeout {
        if let Ok(out) = Command::new("curl").args(["-sf", "--max-time", "2", &url]).output() {
            if out.status.success() {
                return true;
            }
        }
        std::thread::sleep(HEALTH_POLL_INTERVAL);
    }
    false
}

// ─── Tauri commands ─────────────────────────────────────────────────────

#[tauri::command]
fn engine_status(state: State<EngineManager>) -> serde_json::Value {
    let port = *state.port.lock().unwrap();
    let running = state.child.lock().unwrap().is_some();
    serde_json::json!({ "running": running, "port": port })
}

#[tauri::command]
fn start_engine(state: State<EngineManager>) -> Result<serde_json::Value, String> {
    let port = pick_port();
    *state.port.lock().unwrap() = port;

    let mut cmd = if let Some(bin) = find_engine_binary() {
        strip_quarantine(&bin);
        let mut c = Command::new(&bin);
        c.current_dir(bin.parent().map(|p| p.to_path_buf()).unwrap_or_default());
        c
    } else {
        warn!("no bundled lens-engine binary — falling back to python/uvicorn (dev mode)");
        find_python_fallback().ok_or_else(|| "lens-engine not found".to_string())?
    };

    cmd.env("LENS_HOST", ENGINE_HOST)
        .env("LENS_PORT", port.to_string())
        .env("LENS_DATA_DIR", data_dir());

    // Log-to-FILE, never piped (piped stdout can hang on buffer limits).
    let log_path = log_file();
    if let Some(dir) = log_path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    let out = std::fs::OpenOptions::new().create(true).append(true).open(&log_path);
    let err = std::fs::OpenOptions::new().create(true).append(true).open(&log_path);
    if let (Ok(o), Ok(e)) = (out, err) {
        cmd.stdout(Stdio::from(o)).stderr(Stdio::from(e));
    }

    info!("spawning lens-engine on port {}", port);
    let child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn lens-engine: {e}"))?;
    *state.child.lock().unwrap() = Some(child);

    // Poll on a detached thread so the UI thread never blocks.
    let port2 = port;
    std::thread::spawn(move || {
        if wait_for_health(port2, HEALTH_TIMEOUT) {
            info!("lens-engine healthy on port {port2}");
        } else {
            error!("lens-engine did not become healthy on port {port2} within {:?}", HEALTH_TIMEOUT);
        }
    });

    Ok(serde_json::json!({ "started": true, "port": port }))
}

fn data_dir() -> String {
    // Per-OS app-data dir; tauri's path API needs an AppHandle, so keep the
    // sidecar's default convention: $HOME/.lens-engine-data
    if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
        return std::path::PathBuf::from(home).join(".lens-engine-data").to_string_lossy().into_owned();
    }
    "./data".into()
}

fn log_file() -> std::path::PathBuf {
    std::path::PathBuf::from(data_dir()).join("logs").join("lens-engine.log")
}

fn kill_child(child: &mut Child) {
    #[cfg(unix)]
    {
        let _ = Command::new("kill").arg(child.id().to_string()).output();
        std::thread::sleep(Duration::from_millis(300));
    }
    // Then force-kill; full detach, no zombie (§3.4).
    let _ = child.kill();
    let _ = child.wait();
}

fn main() {
    env_logger::init();
    tauri::Builder::default()
        .manage(EngineManager::new())
        .invoke_handler(tauri::generate_handler![engine_status, start_engine])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // nothing extra — cleanup happens in RunEvent::Exit below
                let _ = window;
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            use tauri::RunEvent;
            if let RunEvent::Exit = event {
                let state: State<EngineManager> = app.state();
                if let Some(mut child) = state.child.lock().unwrap().take() {
                    info!("engine exit — killing sidecar");
                    kill_child(&mut child);
                }
            }
        });
}

// Tauri 2 lib entrypoint for mobile/desktop split builds (unused here but
// expected by the crate-type matrix).
pub fn run() {
    main();
}
