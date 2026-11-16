fn main() {
    // Só estes comandos existem para a interface; a capability em tauri.conf.json diz quem pode chamá-los.
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(&["sessao_motor"])),
    )
    .expect("falha no build do Tauri");
}
