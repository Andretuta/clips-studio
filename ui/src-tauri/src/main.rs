use std::path::PathBuf;

use tauri::webview::NewWindowResponse;
use tauri::{Manager, Url, WebviewUrl, WebviewWindowBuilder};

/// A chave de sessão do motor, lida do arquivo a cada pedido: sobrevive ao reinício do motor,
/// que grava uma chave nova. O caminho vem do lançador (CLIPADOR_SESSAO).
#[tauri::command]
fn sessao_motor() -> Result<String, String> {
    let caminho = std::env::var_os("CLIPADOR_SESSAO").ok_or("CLIPADOR_SESSAO não definido")?;
    std::fs::read_to_string(caminho)
        .map(|chave| chave.trim().to_owned())
        .map_err(|erro| erro.to_string())
}

fn main() {
    let verifying = cfg!(debug_assertions) && std::env::args().any(|arg| arg == "--verificar");
    let result = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![sessao_motor])
        .setup(move |app| {
            let frontend = Url::parse("http://localhost:5173/")?;
            let frontend_origin = frontend.origin();

            let mut window = WebviewWindowBuilder::new(app, "clipador", WebviewUrl::External(frontend))
                .title("Clips Kitty — Tauri")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1080.0, 700.0)
                .devtools(false)
                .on_navigation(move |url| url.origin() == frontend_origin)
                .on_new_window(|_, _| NewWindowResponse::Deny);
            // Perfil do WebView2 no disco D (o padrão fica em %LOCALAPPDATA%, no C).
            if let Some(dir) = std::env::var_os("CLIPADOR_WEBVIEW_DIR") {
                window = window.data_directory(PathBuf::from(dir));
            }
            if verifying {
                window
                    .initialization_script(include_str!("verificar.js"))
                    .on_document_title_changed(|view, title| {
                        if let Some(report) = title.strip_prefix("clipador-verificar:") {
                            println!("{report}");
                            view.app_handle()
                                .exit(if report.starts_with("ok ") { 0 } else { 1 });
                        }
                    })
                    .build()?;
            } else {
                window.build()?;
            }
            Ok(())
        })
        .run(tauri::generate_context!());

    if let Err(error) = result {
        eprintln!("Falha ao iniciar a janela Tauri do Clipador: {error}");
        std::process::exit(1);
    }
}
