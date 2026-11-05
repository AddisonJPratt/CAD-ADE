# Magic CAD desktop development shell

This is a Tauri 2 development shell around the existing First Proof app. It is
not yet a distributable app: it requires the repository and its `.venv` at the
same path where the Rust binary was compiled. Bundling a relocatable Python and
CAD runtime, signing, and an installation test remain to be done. The physical
First Proof gate (five actual prints) also remains unmet.

On a Mac with Rust, Tauri 2 CLI and the project Python environment installed:

```sh
cd desktop
cargo tauri dev
```

The shell starts a dedicated local server on `127.0.0.1:8766`, refuses to start
if that port is occupied, and opens its window only after a per-launch handshake.
The shell is designed to stop its server and CAD subprocesses when closed; this
lifecycle has not yet been tested in a running Tauri app. On a subsequent server
start, interrupted makes are marked failed. The shell has a startup recovery
page and writes error details to the terminal; this UI also needs a native test.

Desktop keeps its makes, calibration, generated briefs and print log in Tauri's
per-user application data directory, separate from the browser version's files in
the project. Existing browser history is not migrated automatically. Neither
location is overwritten by starting the other version.

The Linux build needs Rust and the Tauri 2 development libraries including
WebKitGTK 4.1. A native build and actual desktop launch must be verified on the
target OS before distribution.

Here, `cargo check` stopped during system-library discovery: `glib-2.0.pc`
was not available. WebKitGTK 4.1 development files are also missing. The Rust
shell has been formatted but has not been compiled or run in this environment.
