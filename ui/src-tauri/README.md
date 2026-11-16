# Janela Tauri do Clipador

Primeiro bloco da migração da interface no Windows. A janela usa o WebView2 e carrega a interface React de desenvolvimento em `http://localhost:5173`. A interface consulta o motor local na porta `8765`.

## Abrir

1. Inicie o motor com `cola\iniciar.cmd` se a porta `8765` estiver parada.
2. Se a interface estiver parada, mantenha `cola\abrir-app.cmd --web` aberto em outro terminal.
3. Execute `cola\abrir-tauri.cmd`. O primeiro build do Cargo baixa e compila as dependências em `cache` no disco D.

O perfil da janela é próprio. Nesta etapa, ela usa as funções disponíveis no modo web e restringe a navegação à origem local. Seleção nativa de arquivos, sessão privilegiada, OAuth externo e instalador são etapas posteriores. A operação diária usa o lançador habitual.

Para testar uma Mesa com cortes, use `cola\abrir-tauri.cmd --verificar`. O ensaio abre a interface, consulta o motor, decodifica um quadro com a prévia silenciada e encerra a janela de teste com o resultado no terminal.

## Atualização em blocos

1. Validar janela, Mesa, Fila e prévia no mudo. Medir o consumo da interface com a mesma tela aberta.
2. Adaptar operações nativas necessárias para importar, exportar e reconectar ao motor de forma segura.
3. Medir transcrição, análise e renderização separadamente em blocos de captura. Comparar RAM, VRAM, tempo e saída antes de migrar cada rotina.

A análise visual do motor já reduz os quadros a sinais de movimento e brilho conforme o FFmpeg os entrega. No ensaio com um vídeo sintético de 20 minutos, o pico de memória residente do processo Python foi de 333 MiB na versão anterior e 38 MiB com a mudança. Foram duas execuções independentes de cada versão, com séries de sinais idênticas. Esse resultado mede a etapa de análise visual.
