//! Local development shell. The Python CAD runtime is supplied by the checkout.
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

const ADDRESS: &str = "127.0.0.1:8766";
const ORIGIN: &str = "http://127.0.0.1:8766/";

struct Server(Mutex<Option<Child>>);

fn stop_server(child: &mut Child) {
    // The Python server launches the CAD harness and workers. Stop the whole
    // dedicated group so closing the window cannot orphan active CAD builds.
    #[cfg(unix)]
    unsafe {
        libc::kill(-(child.id() as i32), libc::SIGKILL);
    }
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .status();
    }
    let _ = child.kill();
    let _ = child.wait();
}

impl Drop for Server {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.0.lock() {
            if let Some(mut child) = guard.take() {
                stop_server(&mut child);
            }
        }
    }
}

fn wait_for_server(child: &mut Child, nonce: &str) -> Result<(), String> {
    let addr: SocketAddr = ADDRESS
        .parse()
        .map_err(|e| format!("Invalid address: {e}"))?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
            return Err(format!(
                "The local CAD engine exited before startup: {status}"
            ));
        }
        if let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(150)) {
            let _ = stream.set_read_timeout(Some(Duration::from_millis(300)));
            let request = format!(
                "GET /__desktop_ready HTTP/1.1\r\nHost: {ADDRESS}\r\nConnection: close\r\n\r\n"
            );
            let mut response = String::new();
            if stream.write_all(request.as_bytes()).is_ok()
                && stream.take(4096).read_to_string(&mut response).is_ok()
            {
                if let Some((headers, body)) = response.split_once("\r\n\r\n") {
                    if headers.starts_with("HTTP/1.0 200 ") && body == nonce {
                        return Ok(());
                    }
                }
            }
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err("The local CAD engine did not become ready. Check that port 8766 is free and the Python environment is installed.".into())
}

fn start_server(app: &tauri::App) -> Result<Child, String> {
    // Never attach to or terminate another process already listening on the port.
    let available = TcpListener::bind(ADDRESS).map_err(|_| {
        "Port 8766 is already in use. Close the other Magic CAD server and try again.".to_string()
    })?;
    drop(available);
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .ok_or("Project folder missing")?
        .to_path_buf();
    #[cfg(windows)]
    let python = root.join(".venv/Scripts/python.exe");
    #[cfg(not(windows))]
    let python = root.join(".venv/bin/python");
    if !python.is_file() {
        return Err(format!(
            "Python environment not found at {}. Follow MAC_SETUP.md first.",
            python.display()
        ));
    }
    let data = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&data).map_err(|e| e.to_string())?;
    let nonce = uuid::Uuid::new_v4().to_string();
    let mut command = Command::new(python);
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = command
        .arg(root.join("proof/server.py"))
        .current_dir(&root)
        .env("MAGIC_PROOF_DATA", data.join("proof"))
        .env("MAGIC_PROOF_BRIEFS", data.join("briefs"))
        .env("MAGIC_PROOF_PRINT_LOG", data.join("PRINT_LOG.md"))
        .env("MAGIC_PROOF_DESKTOP_TOKEN", &nonce)
        .spawn()
        .map_err(|e| format!("Could not start the local CAD engine: {e}"))?;
    if let Err(error) = wait_for_server(&mut child, &nonce) {
        stop_server(&mut child);
        return Err(error);
    }
    Ok(child)
}

fn main() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let child = match start_server(app) {
                Ok(child) => child,
                Err(error) => {
                    eprintln!("Could not start Magic CAD: {error}");
                    WebviewWindowBuilder::new(
                        app,
                        "startup-error",
                        WebviewUrl::App("index.html".into()),
                    )
                    .title("Magic CAD could not start")
                    .inner_size(600.0, 320.0)
                    .build()?;
                    return Ok(());
                }
            };
            app.manage(Server(Mutex::new(Some(child))));
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(ORIGIN.parse()?))
                .title("Magic CAD")
                .inner_size(1280.0, 820.0)
                .min_inner_size(390.0, 600.0)
                .on_navigation(|url| {
                    url.scheme() == "http"
                        && url.host_str() == Some("127.0.0.1")
                        && url.port() == Some(8766)
                })
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Could not start Magic CAD desktop");
    app.run(|handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Some(server) = handle.try_state::<Server>() {
                if let Ok(mut guard) = server.0.lock() {
                    if let Some(mut child) = guard.take() {
                        stop_server(&mut child);
                    }
                }
            }
        }
    });
}
