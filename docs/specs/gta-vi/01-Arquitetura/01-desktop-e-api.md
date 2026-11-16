# Desktop, API local e credenciais

Estado `ready-for-agent`. Prioridade P0.

Protótipo Tauri validado com a API, a Mesa, uma prévia no mudo e a chave de sessão (`sessao: 200`). A próxima etapa é completar as funções nativas para operação diária.

## Problema

A janela do Clipador, a interface web e a Cola chamam o mesmo motor. A sessão protege algumas ações, enquanto outros caminhos usam apenas o endereço local. As permissões herdadas do disco também abrangem arquivos de configuração e código.

## Solução

Adicionar a janela Tauri por etapas usando o frontend React e o motor Python existentes. Restringir cada ação à conta ou ao cliente que precisa dela e recuperar a sessão após reinício. Manter Electron e modo web disponíveis durante o ensaio.

## Histórias de usuário

1. Como operador, quero que só minha sessão execute ações sobre projetos e canais para impedir mudanças por outro cliente local.
2. Como operador, quero que o supervisor consiga reabrir o motor e a janela recupere a sessão para manter o Controle acessível.
3. Como operador, quero abrir o modo web quando o Electron falhar para continuar usando Mesa, Fila e Publicação.
4. Como operador, quero saber quais portas estão em uso antes de abrir a interface para evitar conectar ao processo errado.
5. Como mantenedor, quero que o software valide a janela de origem de cada ação nativa para preservar a fronteira entre navegador e desktop.
6. Como operador, quero guardar chaves e históricos em locais com permissões adequadas para evitar acesso por outras contas do Windows.
7. Como mantenedor, quero instalar e validar o Tauri em ambiente de teste para promover a janela após passar pelo fluxo diário.
8. Como editor, quero escolher arquivos e pastas no Tauri para importar, revisar e exportar pelo mesmo motor.
9. Como operador, quero abrir OAuth no navegador e voltar à janela com o estado atualizado para conectar minhas contas.

## Decisões de implementação

- Tauri 2 em Rust abre o React no WebView2. O protótipo carrega a interface local na porta `5173` e consulta o motor Python na porta `8765`. A janela tem perfil próprio e o supervisor mantém o motor como processo independente.
- **Sessão local, feita em 16/11 (`672a7ce`).** O comando Rust `sessao_motor` lê `CLIPADOR_SESSAO` (o `session.secret`) a cada pedido e devolve a chave à interface. A capability `sessao-do-motor` libera só esse comando e só para `http://localhost:5173/*`, e o `build.rs` declara a lista de comandos. O perfil do WebView2 vai para `CLIPADOR_WEBVIEW_DIR`, no D. Limite: a janela confia no que escutar na `5173`. O frontend empacotado tira esse limite.
- **Frontend empacotado, revisão Hydrogen xhigh integrada e executável validado pelo Codex em 16/11.** `frontendDist` aponta para `ui/out/renderer`. O comando `npx --no-install tauri build --no-bundle -- --locked` habilita `tauri/custom-protocol`; `cfg(dev)` seleciona Vite e `cfg(not(dev))` seleciona os assets embutidos. A escolha acompanha o modo real do Tauri, inclusive em build empacotado com `--debug`, e não o perfil de otimização do Cargo. A origem do app Windows empacotado é `http://tauri.localhost`.
  - **Permissão local e navegação.** Foi removida a capability remota `sessao-do-motor-dev`. Uma única capability local autoriza `sessao_motor` na janela `clipador`; no desenvolvimento, o próprio Tauri trata `devUrl` como local. A navegação exige a origem exata escolhida, sem usuário ou senha na URL, e novas janelas são negadas. Foi removida a aceitação por prefixo de `tauri://localhost`. O cenário de iframe remoto apontado na revisão dependia de relaxar a CSP atual; a remoção da permissão fecha também esse caminho futuro.
  - **Sessão sem lançador e contas conectadas.** `SESSAO_PADRAO` e `WEBVIEW_PADRAO` ficam no D:, com sobreposição opcional por variável. A sessão é relida a cada pedido. `connectedAccounts.ts` passou a usar `sessionSecret()`, como a Mesa, em vez de depender do preload Electron ausente no Tauri. O teste do cliente foi executado antes da correção e falhou com `no_session`; depois passou com autenticação Tauri, troca da chave, Electron e recusa sem sessão. O harness também voltou a resolver a tradução, que antes impedia esses casos de rodar.
  - **Build e instalador separados.** `bundle.active` está desligado e o build usa `--no-bundle`. `RUSTUP_HOME`, `PATH`, Cargo, npm, TMP e TEMP ficam no D:. O lançador de desenvolvimento também fixa Rust e temporários no D:. O instalador permanece pendente até configurar o cache de suas ferramentas fora do C:.
  - **CORS entregue.** `bea3eea` acrescentou `http://tauri.localhost` preservando as duas origens Vite. Às 15h07, `/health` respondeu `ok` e o preflight aceitou a origem do Tauri. A suíte completa encerrou com 5.480 aprovados, 119 falhas, 19 ignorados e zero erros. Os 40 testes de contrato passaram. O [relatório amplo](../90-Auditorias/suite-completa-2026-11-16.md) lista as falhas e os limites de atribuição; o aceite dirigido da janela não comprova a suíte ampla.
  - **Verificação proporcional.** O relatório `--verificar` inclui a origem real, aguarda a montagem do React e consulta uma rota protegida sem imprimir a chave. Com mídia, decodifica um quadro silenciado; com Mesa vazia, registra `preview: sem_cortes`. Ele não prova todo o editor, botões de decisão, WebSocket ou publicação. `npm run typecheck`, o teste do cliente de contas e `npm run build` passaram após as correções. Build nativo concluído com `npx --no-install tauri build --no-bundle -- --locked`. O ensaio registrou `origin: http://tauri.localhost`, `engine: true`, `pendentes: 105`, `sessao: 200`, `react: true`, `width: 1080`, `muted: true` e `preview: quadro_decodificado`, com a porta 5173 fechada. A Mesa foi inspecionada pela captura real e pela árvore de acessibilidade; a janela ficou aberta. Não foram aprovados, descartados ou publicados cortes.
- Evoluir a ponte nativa aos poucos: seleção de arquivos e pastas, exportação e abertura de OAuth no navegador. Usar operações específicas da interface com permissões mínimas.
- Manter o motor em loopback. Exigir autenticação para API de escrita e leitura sensível. Dar credencial própria e escopo mínimo à Cola e às integrações.
- Definir origens exatas para a interface web, a janela instalada e a conexão de eventos. Validar o identificador da janela, o frame e a navegação permitida antes de cada IPC privilegiado.
- Limitar links externos a protocolos e destinos necessários. A página de doação deve permanecer isolada das funções nativas.
- Verificar permissões efetivas de código, sessão, configuração, mídia e estado para as contas que realmente operam o motor e a Cola. Persistir chaves no cofre do sistema e excluir o acesso de grupos amplos.
- Definir como a janela descobre uma sessão nova e recupera o estado visual. O modo web deve ter bootstrap autenticado e estado equivalente nos fluxos da estreia.
- Ensaiar instalador e atualização do Tauri depois de validar as ações nativas. Usar o fluxo atual na cobertura até a validação de ponta a ponta. Verificar a reversão para o lançador Electron e a alternativa web.

## Decisões de teste

- Costura principal: inicialização do processo e testes de contrato da API. Verificar autorização por perfil e recuperação após iniciar um motor novo, com identidades de teste.
- Para IPC, testar políticas de destino e autorização por unidade e conferir os fluxos de escolher arquivo, idioma e abrir OAuth na janela instalada.
- Verificar permissões em ambiente controlado do Windows sob as contas de serviço previstas. Cobrir leitura e alteração somente de arquivos sintéticos.
- Reaproveitar os testes de sessão, segurança de caminhos, contrato e modo web. Ensaiar a janela nativa e a alternativa web no Windows.
- Repetir a verificação do protótipo com a Mesa carregada e a prévia no mudo. Para promover a janela, completar um ensaio de importar, gerar, revisar, exportar e recuperar a sessão após reiniciar o motor.
- Comparar a memória das janelas com a mesma tela, mesma mídia e API no mesmo estado. Conferir o encerramento sem erro de ciclo de vida do WebView2.

## Fora do escopo

Exposição do motor na internet, reescrita integral do motor em Rust e instalação de complementos novos para a estreia.

## Notas

A solução deve manter prévias no mudo e interfaces em português do Brasil. A verificação via WebView2 saiu com código `0` e registrou o aviso `1412` ao fechar. A captura de tela automatizada expirou. Relaciona-se aos achados R01, R02 e R03.

## Evidência do executável de 16/11

- Executável: `D:/clipador-gta6/cache/tauri-target/release/clipador-tauri.exe`. SHA-256 `7383ea7e791c3ab6885a05c20b68935d7f90c2a9a3d0317f547fef7e483c97c2`.
- Relatório: `D:/clipador-gta6/cache/tauri-verificacao-20261116-1530.json`, gerado pelo próprio executável com `--verificar --relatorio=...`, sem credenciais.
- Captura da Mesa: `D:/clipador-gta6/cache/tauri-mesa-20261116-validada.png`.
- Aprovação, descarte, publicação, importação e OAuth não foram executados neste aceite. O ensaio de mídia usa um elemento de vídeo silenciado próprio; a captura visual comprova a Mesa montada com a prévia, sem substituir o ensaio completo do editor.

Commits desta entrega: `clips-kitty 14cc0e5` (empacotamento, sessão, teste e evidências) e `cola 27079eb` (Rust e temporários no D: no lançador). Sem push.

## Consumo: Electron contra Tauri (16/11/2026, 19h40)

Mesma tela nos dois, a Mesa com 107 cortes. Medido pela árvore de processos de cada app, somando a raiz e todos os filhos (`Get-Process`: `PrivateMemorySize64` e `WorkingSet64`).

| Medida | Electron hoje (`cola\abrir-app.cmd` → `npm run dev`) | Tauri empacotado | Diferença |
| --- | --- | --- | --- |
| Memória privada | 805 MiB | 352 MiB | −453 MiB (−56%) |
| Memória residente (WS) | 964 MiB | 221 MiB | −743 MiB (−77%)¹ |
| Processos | 15 (5 electron, 4 node, esbuild, cmd/conhost) | 9 (7 msedgewebview2, exe, conhost) | −6 |
| Runtime do app em disco | 259 MiB (`node_modules/electron/dist`) + `node_modules` (0,50 GiB) | 9,0 MiB (`clipador-tauri.exe`, React embutido) | −250 MiB só no runtime |

¹ O Tauri estava aberto em segundo plano havia horas, com o WS já aparado pelo Windows. O Electron foi medido 60 s depois de abrir. Por isso a comparação justa é a da memória privada.

- **De onde vem o ganho:** comparando só o motor do navegador, os dois ficam parecidos: Electron com 362 MiB privados e WebView2 mais o exe com 345 MiB. A economia está em não precisar de Node, Vite e esbuild rodando (426 MiB privados), porque o executável já leva o frontend dentro. De quebra, a porta 5173 não fica aberta e nenhum processo pode se passar pela interface.
- **Abertura:** o Electron mostrou a janela em 21 s, contando o `npm run dev`. O Tauri rodou o `--verificar` completo em 18 s: origem, motor, sessão 200, React e um quadro de vídeo decodificado (relatório em `cache/tauri-verificacao-1945.json`). As medidas não são equivalentes; o Tauri faz mais coisas nesse tempo.
- **Custo, só no build:**
  - `D:\rust`: 5,79 GiB;
  - `cache\tauri-target`: 3,71 GiB (pode ser limpo, guardando o exe);
  - `cache\tauri-cargo`: 0,31 GiB;
  - perfil do WebView2: 0,18 GiB.
- **Para liberar no C::** a cópia antiga em `C:\Users\andre\.rustup` + `.cargo` soma 1,72 GiB, já com cartão P2 no quadro.
- **Fora do Rust, mas do mesmo plano:** a análise visual em lotes do motor (Python) caiu de 333 para 38 MiB de pico.
