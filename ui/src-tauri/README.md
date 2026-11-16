# Janela Tauri do Clipador

Primeiro bloco da migração da interface no Windows. A janela usa o WebView2 e carrega a interface React de desenvolvimento em `http://localhost:5173`. A interface consulta o motor local na porta `8765`.

## Abrir

1. Inicie o motor com `cola\iniciar.cmd` se a porta `8765` estiver parada.
2. Se a interface estiver parada, mantenha `cola\abrir-app.cmd --web` aberto em outro terminal.
3. Execute `cola\abrir-tauri.cmd`. O primeiro build do Cargo baixa e compila as dependências em `cache` no disco D.

A janela usa as funções do modo web e restringe a navegação à origem local. Desde 16/11 ela também recebe a chave de sessão do motor, então aprovar, descartar e editar na Mesa funcionam.

- **Chave de sessão.** O comando `sessao_motor` lê `CLIPADOR_SESSAO`, que o `abrir-tauri.cmd` aponta para `data\plugins\session.secret`. O arquivo é lido a cada pedido, então a chave continua valendo depois que o motor reinicia. A capability `sessao-do-motor` em `tauri.conf.json` libera só esse comando, e só para `http://localhost:5173/*`. O `build.rs` declara a lista de comandos.
- **Perfil do WebView2.** Fica em `cache\tauri-webview`, no D, pela variável `CLIPADOR_WEBVIEW_DIR`.
- **Limite.** A janela confia no que estiver escutando na porta `5173`. Use-a só com o Vite do projeto no ar.
- **Etapas posteriores.** Seleção nativa de arquivos, OAuth no navegador, frontend empacotado sem Vite e instalador. A operação diária usa o lançador habitual.

Para testar, use `cola\abrir-tauri.cmd --verificar`. O ensaio abre a interface, consulta o motor, confere a chave de sessão numa rota protegida (`sessao: 200`), decodifica um quadro com a prévia silenciada e fecha a janela com o resultado no terminal.

## Atualização em blocos

1. Validar janela, Mesa, Fila e prévia no mudo. Medir o consumo da interface com a mesma tela aberta.
2. Adaptar operações nativas necessárias para importar, exportar e reconectar ao motor de forma segura.
3. Medir transcrição, análise e renderização separadamente em blocos de captura. Comparar RAM, VRAM, tempo e saída antes de migrar cada rotina.

A análise visual do motor já reduz os quadros a sinais de movimento e brilho conforme o FFmpeg os entrega. No ensaio com um vídeo sintético de 20 minutos, o pico de memória residente do processo Python foi de 333 MiB na versão anterior e 38 MiB com a mudança. Foram duas execuções independentes de cada versão, com séries de sinais idênticas. Esse resultado mede a etapa de análise visual.
