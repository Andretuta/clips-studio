use std::path::PathBuf;

use tauri::webview::NewWindowResponse;
use tauri::{Manager, Url, WebviewUrl, WebviewWindowBuilder};

/// A origem que a janela aceita.
///
/// Em desenvolvimento a interface vem do Vite. No release ela vem de dentro do binário
/// (`frontendDist`), servida pelo protocolo do Tauri, que no Windows chega como
/// `http://tauri.localhost` — é o contorno do wry para o WebView2. A janela empacotada
/// não depende mais da porta 5173, então nenhum processo que ocupe essa porta recebe a
/// chave de sessão do motor.
#[cfg(dev)]
const ORIGEM: &str = "http://localhost:5173/";
#[cfg(not(dev))]
const ORIGEM: &str = "http://tauri.localhost/";

/// Onde está a chave de sessão quando o lançador não diz, que é o caso do app instalado:
/// o `abrir-tauri.cmd` define `CLIPADOR_SESSAO`, um atalho do menu Iniciar não.
// ponytail: caminho fixo da instalação única desta máquina. `CLIPADOR_SESSAO` continua
// sobrepondo; se o app passar a ser instalado em outro lugar, ler de um arquivo ao lado do .exe.
const SESSAO_PADRAO: &str = r"D:\clipador-gta6\data\plugins\session.secret";

/// Perfil do WebView2 quando o lançador não diz. Sem isto o app instalado escreveria o perfil
/// em `%LOCALAPPDATA%`, no C:, que é disco cheio e está vetado neste projeto.
const WEBVIEW_PADRAO: &str = r"D:\clipador-gta6\cache\tauri-webview";

/// A chave de sessão do motor, lida do arquivo a cada pedido: sobrevive ao reinício do motor,
/// que grava uma chave nova.
#[tauri::command]
fn sessao_motor() -> Result<String, String> {
    let caminho = std::env::var_os("CLIPADOR_SESSAO")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(SESSAO_PADRAO));
    std::fs::read_to_string(&caminho)
        .map(|chave| chave.trim().to_owned())
        .map_err(|erro| format!("{}: {erro}", caminho.display()))
}

fn main() {
    // Vale também no release: é a única conferência automática do caminho empacotado (frontend
    // embutido, origem nova, caminhos padrão). Sem o argumento, o roteiro não é injetado.
    let verifying = std::env::args().any(|arg| arg == "--verificar");
    let relatorio =
        std::env::args().find_map(|arg| arg.strip_prefix("--relatorio=").map(PathBuf::from));
    let result = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![sessao_motor])
        .setup(move |app| {
            let origem = Url::parse(ORIGEM)?.origin();
            if verifying {
                println!(
                    "clipador-origem: esperada {:?}",
                    origem.ascii_serialization()
                );
            }

            #[cfg(dev)]
            let destino = WebviewUrl::External(Url::parse(ORIGEM)?);
            #[cfg(not(dev))]
            let destino = WebviewUrl::App(PathBuf::from("index.html"));

            let mut window = WebviewWindowBuilder::new(app, "clipador", destino)
                .title("Clips Kitty — Tauri")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1080.0, 700.0)
                .devtools(false)
                // Apenas a origem escolhida pelo modo Tauri pode navegar nesta janela.
                .on_navigation(move |url| {
                    let permitido = url.origin() == origem
                        && url.username().is_empty()
                        && url.password().is_none();
                    if verifying {
                        println!(
                            "clipador-navegacao: {url} -> {}",
                            if permitido { "permitido" } else { "BARRADO" }
                        );
                    }
                    permitido
                })
                .on_new_window(|_, _| NewWindowResponse::Deny);
            // Perfil do WebView2 sempre no disco D (o padrão do WebView2 fica em %LOCALAPPDATA%).
            let perfil = std::env::var_os("CLIPADOR_WEBVIEW_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| PathBuf::from(WEBVIEW_PADRAO));
            window = window.data_directory(perfil);
            if verifying {
                window
                    .initialization_script(include_str!("verificar.js"))
                    .on_document_title_changed(move |view, title| {
                        if let Some(report) = title.strip_prefix("clipador-verificar:") {
                            println!("clipador-verificar:{report}");
                            if let Some(caminho) = &relatorio {
                                let json =
                                    report.split_once(' ').map(|(_, json)| json).unwrap_or("{}");
                                if let Err(erro) = std::fs::write(caminho, json) {
                                    eprintln!("Falha ao gravar o relatório de verificação: {erro}");
                                    view.app_handle().exit(1);
                                    return;
                                }
                            }
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
