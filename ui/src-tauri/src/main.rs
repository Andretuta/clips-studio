use tauri::webview::NewWindowResponse;
use tauri::{Manager, Url, WebviewUrl, WebviewWindowBuilder};

fn main() {
    let verifying = cfg!(debug_assertions) && std::env::args().any(|arg| arg == "--verificar");
    let result = tauri::Builder::default()
        .setup(move |app| {
            let frontend = Url::parse("http://localhost:5173/")?;
            let frontend_origin = frontend.origin();

            let window = WebviewWindowBuilder::new(app, "clipador", WebviewUrl::External(frontend))
                .title("Clips Kitty — Tauri")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1080.0, 700.0)
                .devtools(false)
                .on_navigation(move |url| url.origin() == frontend_origin)
                .on_new_window(|_, _| NewWindowResponse::Deny);
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
