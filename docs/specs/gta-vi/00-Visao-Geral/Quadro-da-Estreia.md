---

kanban-plugin: board

---

## Depende do usuário

- [ ] Reiniciar a Cola para valer o garimpeiro: fechar a janela "Cola" e rodar `D:\clipador-gta6\cola\iniciar.cmd cola`. O processo de 15/11 ainda usa BaianoTV no LoL #P0 [estado](ESTADO-OPERACIONAL.md)
- [ ] Conectar YouTube e/ou TikTok (Composio ou OAuth direto) e fazer um envio privado de ensaio #P1 [spec](../04-Mesa-e-publicacao/09-publicacao-e-contas.md)
- [ ] Ligar a autorização de automação do plano ChatGPT se a Cola for processar sozinha #P1 [spec](../03-Producao-de-clips/05-ia-e-transcricao.md)
- [ ] Reiniciar o motor (análise em lotes, `bloco_s` na Mesa) e abrir de novo a janela Tauri ou o app #P1 [estado](ESTADO-OPERACIONAL.md)
- [ ] R01: rodar os 3 comandos `icacls` do estado operacional (dá controle total ao `andre`, corta a herança do D: e tira `Usuários autenticados` e `Usuários`) #P0 #R01 [estado](ESTADO-OPERACIONAL.md)
- [ ] Opcional: apagar a cópia antiga do rustup em `C:\Users\andre\.rustup` + `.cargo` (1,6 GB) e o perfil WebView2 antigo do Tauri no C: (137 MB) #P2
- [ ] Push para o GitHub: `gta6-melhorias` (9 commits) e o novo `codex-estreia` #P2


## A fazer · P0 (antes da estreia)

- [ ] Exigir sessão nas mutações da API (fila, publicação) e nas leituras sensíveis #P0 #R02 [spec](../01-Arquitetura/01-desktop-e-api.md)
- [ ] Cola: tirar concatenação e envio do tique; prazos e concorrência por recurso #P0 #R04 [spec](../02-Captura-e-fila/03-gravacao-e-entrega.md)
- [ ] Motor: reservar vaga e bytes antes de importar o bloco #P0 #R05 [spec](../02-Captura-e-fila/04-fila-e-armazenamento.md)
- [ ] Bloco com ID estável, sem apagar quando vier sem job_id; isolar segmento corrompido; órfãos pela identidade completa #P0 #R06 [spec](../02-Captura-e-fila/03-gravacao-e-entrega.md)
- [ ] Twitch Helix: paginação, renovar categorias, respeitar `Ratelimit-Reset` no 429; domínio exato nas URLs #P0 #R07 [spec](../02-Captura-e-fila/02-descoberta-de-lives.md)
- [ ] Orçamento de disco e fila por tipo; compilado não tira vaga da captura #P0 #R08 [spec](../02-Captura-e-fila/04-fila-e-armazenamento.md)
- [ ] Ensaio ponta a ponta pelo garimpeiro: 1º clipe da Twitch → tarefa → corte na Mesa → MP4 com áudio #P0 [estado](ESTADO-OPERACIONAL.md)
- [ ] Ensaio de falhas: motor parado, fila cheia, resposta perdida — o mesmo bloco volta com uma tarefa só #P0 [spec](../05-Operacao/10-observabilidade-e-operacao.md)


## A fazer · P1

- [ ] Medir Whisper + render com um bloco real de 5 min (tempo, RAM, VRAM) #P1 [spec](../03-Producao-de-clips/05-ia-e-transcricao.md)
- [ ] WebSocket: validar Origin e sessão, limitar assinantes #P1 #R10 [auditoria](../90-Auditorias/rev-code-review.md)
- [ ] Mesa: par MP4 + JSON com transição recuperável; paginar a listagem #P1 #R11 [spec](../04-Mesa-e-publicacao/07-mesa-e-controle.md)
- [ ] Compilado: limite de fontes e duração, reserva de espaço #P1 #R12 [spec](../04-Mesa-e-publicacao/08-compilados-youtube.md)
- [ ] Publicação: guardar ID do TikTok, estados aceito/incerto, reconciliar antes de repetir #P1 #R13 [spec](../04-Mesa-e-publicacao/09-publicacao-e-contas.md)
- [ ] Diagnóstico: eventos persistidos com ID de correlação, cache das métricas #P1 #R14 [spec](../05-Operacao/10-observabilidade-e-operacao.md)
- [ ] Caches de prévia, relay e sondagem com expiração #P1 #R15 [auditoria](../90-Auditorias/rev-code-review.md)
- [ ] Webhook: segredo HMAC fora do payload, destinos autorizados #P1 #R16 [auditoria](../90-Auditorias/rev-code-review.md)
- [ ] Electron 31.7.7: política central de links externos e remetente nos IPCs #P1 #R03 [spec](../01-Arquitetura/01-desktop-e-api.md)
- [ ] Tauri: importar/exportar nativo, OAuth no navegador, frontend empacotado sem Vite, build release e instalador #P1 [spec](../01-Arquitetura/01-desktop-e-api.md)


## Fazendo



## Feito

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
