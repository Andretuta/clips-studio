---

kanban-plugin: board

---

## Depende do usuário

- [ ] Conectar YouTube e/ou TikTok (Composio ou OAuth direto) e fazer um envio privado de ensaio #P1 [spec](../04-Mesa-e-publicacao/09-publicacao-e-contas.md)
- [ ] Ligar a autorização de automação do plano ChatGPT se a Cola for processar sozinha #P1 [spec](../03-Producao-de-clips/05-ia-e-transcricao.md)
- [ ] R01: rodar os 3 comandos `icacls` do estado operacional (dá controle total ao `andre`, corta a herança do D: e tira `Usuários autenticados` e `Usuários`) #P0 #R01 [estado](ESTADO-OPERACIONAL.md)
- [ ] Opcional: apagar a cópia antiga do rustup em `C:\Users\andre\.rustup` + `.cargo` (1,6 GB) e o perfil WebView2 antigo do Tauri no C: (137 MB) #P2
- [ ] Push para o GitHub: `gta6-melhorias` (9 commits) e o novo `codex-estreia` #P2


## A fazer · P0 (antes da estreia)



## A fazer · P1

- [ ] Exigir sessão nas mutações da API (fila, publicação) e nas leituras sensíveis #P1 #R02 (segurança adiada pelo usuário em 16/11: roda só na máquina dele) [spec](../01-Arquitetura/01-desktop-e-api.md)
- [ ] Corrigir os seis grupos das 119 falhas da suíte ampla: resolver i18n nos testes Node primeiro, isolar .venv/config/intérprete e verificar legendas antes de mudar expectativas #P1 [relatório](../90-Auditorias/suite-completa-2026-11-16.md)

- [ ] Medir Whisper + render com um bloco real de 5 min (tempo, RAM, VRAM) #P1 [spec](../03-Producao-de-clips/05-ia-e-transcricao.md)
- [ ] WebSocket: validar Origin e sessão, limitar assinantes #P1 #R10 [auditoria](../90-Auditorias/rev-code-review.md)
- [ ] Mesa: par MP4 + JSON com transição recuperável; paginar a listagem #P1 #R11 [spec](../04-Mesa-e-publicacao/07-mesa-e-controle.md)
- [ ] Compilado: limite de fontes e duração, reserva de espaço #P1 #R12 [spec](../04-Mesa-e-publicacao/08-compilados-youtube.md)
- [ ] Diagnóstico: eventos persistidos com ID de correlação, cache das métricas #P1 #R14 [spec](../05-Operacao/10-observabilidade-e-operacao.md)
- [ ] Caches de prévia, relay e sondagem com expiração #P1 #R15 [auditoria](../90-Auditorias/rev-code-review.md)
- [ ] Webhook: segredo HMAC fora do payload, destinos autorizados #P1 #R16 [auditoria](../90-Auditorias/rev-code-review.md)
- [ ] Tauri: importar/exportar nativo e OAuth no navegador #P1 [spec](../01-Arquitetura/01-desktop-e-api.md)
- [ ] Tauri: instalador com cache de NSIS/WiX no D:; `bundle.active` fica desligado até configurar e ensaiar #P2 [spec](../01-Arquitetura/01-desktop-e-api.md)


## Fazendo

- [ ] [Motor] Chat do bloco entra na pontuação; pontuação de momento-chave validada contra clipes reais; inclui R05 e R08 #P0 #antigravity-motor [spec](../03-Producao-de-clips/05-ia-e-transcricao.md)
- [ ] [Electron] Pronto para teste: publicação com OAuth (YouTube/TikTok), R13, análise do R03, autonomia da IA para editar e roteiro de teste #P0 #codex [spec](../04-Mesa-e-publicacao/09-publicacao-e-contas.md)

## Feito

- [x] [Gravação] Lives inteiras: codecs medidos (`-c copy` 1080p60 a 3,23 GiB/h), chat ao vivo da Twitch (IRC TLS) por bloco, ensaio até a Mesa (9,1 min no motor) e R04/R06/R07/R08 na Cola; 100 testes da Cola verdes #P0 #antigravity-gravacao [spec](../02-Captura-e-fila/03-gravacao-e-entrega.md) (Cola `17fa9d6`, `62da4d5`) @{2026-11-16}
- [x] Motor reiniciado às 20h39 com `c6ede52` e `35a226b`, como `andre`, pelo laço do `iniciar.cmd` #P0 #claude [estado](ESTADO-OPERACIONAL.md) @{2026-11-16}
- [x] Revisão da rodada Hydrogen: guarda de resposta perdida corrigida (adotava job alheio), custo do Whisper medido em bloco de 5 min e Cola recarregada #P0 #claude [spec](../05-Operacao/10-observabilidade-e-operacao.md) (Cola c6093ab) @{2026-11-16}
- [x] Consumo Electron × Tauri medido na Mesa: memória privada 805 → 352 MiB, processos 15 → 9, runtime 259 → 9 MiB #P1 #claude [spec](../01-Arquitetura/01-desktop-e-api.md) (afbb0a1) @{2026-11-16}
- [x] Ensaio de falhas: motor parado, fila cheia, resposta perdida — o mesmo bloco volta com uma tarefa só #P0 #antigravity [spec](../05-Operacao/10-observabilidade-e-operacao.md) (`c6ede52`; Cola `5ab6354`) @{2026-11-16}
- [x] Whisper perdeu a fala do clipe 158: transcreveu 4,4 s de 25,5 s → `beam_size=5` na GPU + VAD `0.3` (16 trechos até 25,2 s) #P1 #antigravity [spec](../03-Producao-de-clips/05-ia-e-transcricao.md) (`35a226b`) @{2026-11-16}
- [x] Hashtags fora do tema nos clipes do garimpeiro: incluir o jogo (#GTA6/#GTAV) no título e nas hashtags até o sidecar entregue #P1 #antigravity [spec](../02-Captura-e-fila/02-descoberta-de-lives.md) (Cola `5ab6354`) @{2026-11-16}
- [x] Marca CG ligada por padrão nos cortes da Cola: a entrega grava `cortes_gamer_watermark: true` e a caixa já vem marcada na Mesa; 70 testes da Cola verdes #P0 #claude [spec](../02-Captura-e-fila/02-descoberta-de-lives.md) (Cola dca570b) @{2026-11-16}
- [x] Ensaio ponta a ponta pelo garimpeiro: 2 clipes da Twitch → tarefas 74–77 → `saida/pendentes` → Mesa em 6 min; MP4 1080×1920 com áudio e karaokê verde em PT; marca CG conferida numa cópia #P0 #claude [spec](../02-Captura-e-fila/02-descoberta-de-lives.md) @{2026-11-16}
- [x] Cola reiniciada como `andre`: o laço de 15/11 rodava como `CodexSandboxOffline` (sandbox do Codex, sem internet) e o garimpeiro dava `WinError 10013`; às 19h04 mandou 2 clipes [spec](../02-Captura-e-fila/02-descoberta-de-lives.md) @{2026-11-16}
- [x] Motor reiniciado às 15h03 (análise em lotes e `bloco_s` ativos) e janela Tauri empacotada aberta na Mesa [estado](ESTADO-OPERACIONAL.md) @{2026-11-16}
- [x] Tauri empacotado sem Vite, sessão local e contas conectadas; revisão Hydrogen xhigh integrada e Mesa inspecionada #P1 #codex [spec](../01-Arquitetura/01-desktop-e-api.md) (14cc0e5; Cola 27079eb) @{2026-11-16}

- [x] Motor: aceitar a origem `http://tauri.localhost` no CORS, para a janela empacotada falar com a API #P1 #codex [spec](../01-Arquitetura/01-desktop-e-api.md) (bea3eea) @{2026-11-16}

- [x] Claude e Codex na mesma raiz pelo T3: projeto registrado em `D:\clipador-gta6` com os botões "Estado do cofre" e "Health do motor", protocolo de dupla no `AGENTS.md` e briefing do Codex por `.claude/hooks/estado.py` [spec](Plugins-do-Cofre.md) @{2026-11-16}
- [x] R09: login, limite ou crédito da IA não gasta tentativa nem apaga a fonte; volta a cada 30 min (Cola 66cced8) @{2026-11-16}
- [x] Janela Tauri com a chave de sessão do motor: aprovar, descartar e editar na Mesa; perfil WebView2 no D; `--verificar` com `sessao: 200` (672a7ce, Cola 7f04de7) @{2026-11-16}
- [x] Duração do bloco vem da Cola (`bloco_s`) e a Mesa e o Controle desenham 300 s ou 960 s conforme o corte (353ae66, Cola 60a3131) @{2026-11-16}
- [x] R17: os 6 testes do painel de publicação voltaram a rodar no Node 25 (756d064) @{2026-11-16}
- [x] Trabalho do Codex commitado no branch `codex-estreia`: `clips-kitty` em 141a687 mais o cofre, e a Cola em dc23621, sem push @{2026-11-16}
- [x] Fonte da estreia escolhida: só o garimpeiro (GTA V e VI, 50+ visualizações), sem canais fixos no gravador @{2026-11-16}
- [x] Cofre ligado ao Claude: regras + hooks em `D:/clipador-gta6/.claude`, quadro Kanban e desenho Excalidraw @{2026-11-16}
- [x] Testes do código atual: 215 do motor, 70 da Cola e typecheck verdes @{2026-11-16}
- [x] Análise visual em lotes: pico de RAM 333 → 38 MiB, tempo 3,48 → 1,61 s @{2026-11-16}
- [x] Protótipo Tauri 2 abriu o React, listou a Mesa e tocou a prévia @{2026-11-16}
- [x] Compilado 16:9 exportado com ordem, 1920 × 1080, 30 fps e áudio
- [x] Marca Cortes Gamer (`@CortesGameroffc`) no editor e no render
- [x] API de diagnóstico com sessão (`/diagnostics/*`)
- [x] Blocos de 4 min + 1 min de sobreposição na Cola
- [x] Cola preserva bloco rejeitado sem travar o gravador (58ea6f1)
- [x] Mesa de aprovação + Sala de controle (grafite e âmbar) @{2026-11-14}
- [x] Legenda karaokê verde como padrão do canal @{2026-11-14}




%% kanban:settings
```
{"kanban-plugin":"board","list-collapse":[false,false,false,false,false],"show-checkboxes":true}
```
%%
