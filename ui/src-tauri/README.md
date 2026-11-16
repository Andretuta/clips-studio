# Janela Tauri do Clipador

Janela WebView2 para a interface React. Tem dois modos, e a diferença é de onde vem o HTML:

| Modo | De onde vem a interface | Origem no webview |
| --- | --- | --- |
| Desenvolvimento (`cargo run`, sem `custom-protocol`) | Servidor Vite em `http://localhost:5173` | `http://localhost:5173` |
| Empacotado (`npx tauri build --no-bundle`, inclusive `--debug`) | Arquivos embutidos no binário, de `ui/out/renderer` | `http://tauri.localhost` |

Nos dois casos a interface consulta o motor local na porta `8765`.

## Abrir em desenvolvimento

1. Inicie o motor com `cola\iniciar.cmd` se a porta `8765` estiver parada.
2. Mantenha `cola\abrir-app.cmd --web` aberto em outro terminal.
3. Execute `cola\abrir-tauri.cmd`. O primeiro build do Cargo baixa e compila as dependências em `cache` no disco D.

Para testar, use `cola\abrir-tauri.cmd --verificar`. O ensaio abre a interface, consulta o motor, confere a chave de sessão numa rota protegida (`sessao: 200`), decodifica um quadro com a prévia silenciada e fecha a janela com o resultado no terminal.

## Build release

O `frontendDist` aponta para `../out/renderer`, que é artefato de build e está no `.gitignore`. Então a ordem importa:

```
cd clips-kitty\ui
set RUSTUP_HOME=D:\rust\rustup
set PATH=D:\rust\cargo\bin;%PATH%
set CARGO_HOME=D:\clipador-gta6\cache\tauri-cargo
set CARGO_TARGET_DIR=D:\clipador-gta6\cache\tauri-target
set TMP=D:\clipador-gta6\cache\tmp
set TEMP=D:\clipador-gta6\cache\tmp
set npm_config_cache=D:\clipador-gta6\cache\npm
npm run build
npx --no-install tauri build --no-bundle
```

O binário sai em `cache\tauri-target\release\clipador-tauri.exe` e abre sem Vite e sem a porta 5173.

**Modo do Tauri.** `cfg(dev)` acompanha a feature `custom-protocol`, independentemente de otimização ou símbolos de depuração. O CLI habilita o protocolo de assets e embute o renderer; `cargo build --release` isolado continua em modo de desenvolvimento. O código usa `cfg(dev)` para escolher a URL e a origem de forma coerente com o Tauri.

**Instalador.** `bundle.active` está desligado e o comando mantém `--no-bundle`. O CLI npm está instalado como devDependency. O instalador continua pendente até definir o cache de NSIS/WiX no D:; o executável empacotado pode ser usado diretamente.

## Detalhes

- **Chave de sessão.** O comando `sessao_motor` lê `CLIPADOR_SESSAO`, que o `abrir-tauri.cmd` aponta para `data\plugins\session.secret`. Sem a variável — o caso de um atalho do menu Iniciar — cai no caminho fixo `D:\clipador-gta6\data\plugins\session.secret`. O arquivo é lido a cada pedido, então a chave continua valendo depois que o motor reinicia. O `build.rs` declara a lista de comandos.
- **Capabilities.** Uma única capability local libera `sessao_motor` para a janela `clipador`. Não há permissão `remote` para a porta 5173 no executável empacotado. No modo `cfg(dev)`, o próprio Tauri trata `devUrl` como origem local.
- **Perfil do WebView2.** `CLIPADOR_WEBVIEW_DIR`, com padrão em `cache\tauri-webview`. Nunca no C:.
- **Navegação.** Restrita à origem exata do modo em uso, sem credenciais na URL. Janelas novas são negadas.
- **Limite que sobrou.** Só no build debug: a janela carrega o que estiver na porta `5173`, então um processo que ocupe a porta antes do Vite recebe a chave de sessão. Use o build debug só com o Vite do projeto no ar. No release isso não existe, porque o HTML vem de dentro do binário.
- **Etapas posteriores.** Seleção nativa de arquivos, OAuth no navegador e o instalador.

## Alcance da verificação

`clipador-tauri.exe --verificar` informa a origem real do WebView2, saúde da API, sessão aceita numa rota protegida e montagem do React. Com cortes na Mesa, também decodifica um quadro de vídeo silenciado. Se a Mesa estiver vazia, registra `preview: sem_cortes`, sem afirmar que a mídia foi testada. O ensaio não aprova ou descarta cortes, não publica e não cobre todo o editor nem o WebSocket; essas ações exigem verificações próprias.

Para guardar o resultado sem depender de um terminal visível, acrescente `--relatorio=D:\clipador-gta6\cache\tauri-verificacao.json`. O arquivo contém o relatório JSON sem a chave de sessão; prefira um nome novo para cada ensaio.

O cliente de contas conectadas usa a mesma ponte de sessão da Mesa e dos plugins, inclusive no Tauri. O teste `node scripts/test-connected-accounts.cjs` cobre o preload Electron, a ponte nativa, a troca de chave e a recusa de chamadas sem sessão, com credenciais sintéticas.

## Atualização em blocos

1. Validar janela, Mesa, Fila e prévia no mudo. Medir o consumo da interface com a mesma tela aberta.
2. Adaptar operações nativas necessárias para importar, exportar e reconectar ao motor de forma segura.
3. Medir transcrição, análise e renderização separadamente em blocos de captura. Comparar RAM, VRAM, tempo e saída antes de migrar cada rotina.

A análise visual do motor já reduz os quadros a sinais de movimento e brilho conforme o FFmpeg os entrega. No ensaio com um vídeo sintético de 20 minutos, o pico de memória residente do processo Python foi de 333 MiB na versão anterior e 38 MiB com a mudança. Foram duas execuções independentes de cada versão, com séries de sinais idênticas. Esse resultado mede a etapa de análise visual.
