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

mod ai_backend;

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use log::{error, info, warn};
use tauri::{Manager, State};

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

/// Candidate window. Tauri's CSP lists exactly these ports, so the sidecar
/// never lands on a port the webview is forbidden to call (v0.2.0 lesson).
const PORT_WINDOW: u16 = 5;

fn pick_port() -> u16 {
    let mut port = PARENT_ENGINE_PORT;
    while engine_alive_on(port) && port < PARENT_ENGINE_PORT + PORT_WINDOW {
        info!(
            "port {} busy (possible CorpusMind Text engine or stale engine) — trying next",
            port
        );
        port += 1;
    }
    port
}

// ─── Sidecar discovery ─────────────────────────────────────────────────

/// Arch-suffixed sidecar name (universal macOS builds bundle BOTH
/// `lens-engine-aarch64` and `lens-engine-x86_64`; single-arch builds ship
/// the plain `lens-engine`). `std::env::consts::ARCH` is "aarch64" or
/// "x86_64", matching the PyInstaller artifact names.
fn arch_engine_name() -> String {
    format!("lens-engine-{}", std::env::consts::ARCH)
}

fn find_engine_binary(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;

    let mut candidates: Vec<std::path::PathBuf> = Vec::new();
    let arch_name = arch_engine_name();

    // 1. Bundled resource dir. On macOS resources live in
    //    Contents/Resources (NOT next to the exe in Contents/MacOS), so the
    //    Tauri resource resolver is the only correct lookup there.
    if let Ok(res_dir) = app.path().resolve("lens-engine", tauri::path::BaseDirectory::Resource) {
        candidates.push(res_dir.join(&arch_name));
        candidates.push(res_dir.join("lens-engine"));
        #[cfg(windows)]
        candidates.push(res_dir.join("lens-engine.exe"));
    }

    // 2. Exe-relative fallbacks (Windows/Linux resource layouts, dev runs).
    candidates.push(dir.join(&arch_name));
    candidates.push(dir.join("lens-engine").join("lens-engine"));
    candidates.push(dir.join("lens-engine"));
    #[cfg(windows)]
    {
        candidates.push(dir.join("lens-engine").join("lens-engine.exe"));
        candidates.push(dir.join("lens-engine.exe"));
    }

    let found = candidates.into_iter().find(|c| c.is_file());
    if let Some(p) = &found {
        info!("sidecar binary: {}", p.display());
    }
    found
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

/// Minimal HTTP GET over a raw TcpStream. Previously this shelled out to
/// `curl`, which silently never succeeded on machines without curl on PATH
/// and left the 60-second health budget burning for nothing.
fn http_ok(port: u16, path: &str) -> bool {
    use std::io::{Read, Write};
    let addr = format!("{ENGINE_HOST}:{port}");
    let Ok(mut stream) = std::net::TcpStream::connect(&addr) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let req = format!("GET {path} HTTP/1.1\r\nHost: {ENGINE_HOST}:{port}\r\nConnection: close\r\n\r\n");
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 128];
    let n = stream.read(&mut buf).unwrap_or(0);
    let head = String::from_utf8_lossy(&buf[..n]);
    head.starts_with("HTTP/1.") && (head.contains(" 200") || head.contains(" 204"))
}

fn wait_for_health(port: u16, timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if http_ok(port, "/api/v1/health") {
            return true;
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

/// Shared spawn logic for both the startup hook and the manual command.
fn spawn_engine(app: &tauri::AppHandle, state: &EngineManager, port: u16) -> Result<serde_json::Value, String> {
    *state.port.lock().unwrap() = port;

    let mut cmd = if let Some(bin) = find_engine_binary(app) {
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
    // Hand the shell's machine probe to the engine so /ai/catalog fit
    // badges use the same numbers the Setup screen shows (v0.2).
    cmd.env("LENS_MACHINE_SPECS_JSON", ai_backend::machine_specs().to_string());

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

    #[cfg(windows)]
    {
        // A console-subsystem sidecar spawned by a windows_subsystem="windows"
        // host flashes a console window — suppress it (documented pitfall).
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    info!("spawning lens-engine on port {}", port);
    let child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn lens-engine: {e}"))?;
    *state.child.lock().unwrap() = Some(child);

    // Poll on a detached thread so the UI thread never blocks.
    std::thread::spawn(move || {
        if wait_for_health(port, HEALTH_TIMEOUT) {
            info!("lens-engine healthy on port {port}");
        } else {
            error!("lens-engine did not become healthy on port {port} within {:?}", HEALTH_TIMEOUT);
        }
    });

    Ok(serde_json::json!({ "started": true, "port": port }))
}

#[tauri::command]
fn start_engine(
    app: tauri::AppHandle,
    state: State<EngineManager>,
) -> Result<serde_json::Value, String> {
    let port = pick_port();
    spawn_engine(&app, &state, port)
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
        .manage(ai_backend::AiBackendManager::new())
        .invoke_handler(tauri::generate_handler![
            engine_status,
            start_engine,
            ai_backend::ai_backend_status,
            ai_backend::ai_backend_start,
            ai_backend::ai_backend_restart,
            ai_backend::ai_install_ollama,
            ai_backend::machine_specs_command,
        ])
        .setup(|app| {
            // AUTO-START the sidecar (v0.2.0 rebuild): the released v0.2.0
            // never started its bundled engine at all — no setup hook and no
            // frontend caller — so the packaged app ran permanently offline.
            // Spawn on a detached thread; the window must not wait on PyInstaller
            // first-run scans (Windows Defender) which can take tens of seconds.
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let state = handle.state::<EngineManager>();
                let port = pick_port();
                match spawn_engine(&handle, &state, port) {
                    Ok(_) => info!("engine auto-start accepted on port {port}"),
                    Err(e) => error!("engine auto-start failed: {e}"),
                }
            });
            Ok(())
        })
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
                // Hoist the take() out of the if-let: newer rustc's if-let
                // temporary scoping rejects the chained lock().take() form.
                let mut taken = state.child.lock().unwrap().take();
                if let Some(mut child) = taken.as_mut() {
                    info!("engine exit — killing sidecar");
                    kill_child(child);
                }
                // Kill only the `ollama serve` WE spawned; a user-started
                // daemon keeps running (parent's lesson, one way round).
                ai_backend::shutdown(app.state::<ai_backend::AiBackendManager>().inner());
            }
        });
}

// Tauri 2 lib entrypoint for mobile/desktop split builds (unused here but
// expected by the crate-type matrix).
pub fn run() {
    main();
}
