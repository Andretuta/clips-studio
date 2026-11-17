# Gravação, blocos e entrega ao motor

Estado `implementado na Cola (codex-estreia)`; falta a ingestão do campo `chat` e R05/R08 no lado do motor ([spec 05](../03-Producao-de-clips/05-ia-e-transcricao.md) · [spec 04](04-fila-e-armazenamento.md)). Prioridade P0.

## Problema

Captura, envio e entrega rodam num ciclo síncrono. Uma transferência lenta ou um bloco corrompido pode atrasar outros canais. Reinícios e falhas de disco afetam os arquivos em trânsito.

## Solução

Separar o controle da gravação das transferências. Manter os blocos em fila durável, dar prioridade justa entre canais e apagar apenas após confirmação persistida.

## Histórias de usuário

1. Como operador, quero que novos canais sejam detectados enquanto um bloco é enviado para aproveitar a primeira reação.
2. Como operador, quero que uma fonte lenta preserve o andamento das demais para limitar o efeito de uma falha.
3. Como operador, quero retomar uma transferência depois de perder acesso ao motor sem duplicar a tarefa.
4. Como operador, quero ver quanto espaço os segmentos, blocos e rejeitados consomem para agir antes de o disco encher.
5. Como editor, quero que lances entre dois blocos apareçam no máximo uma vez sem cortar palavras ou reações.
6. Como operador, quero que um segmento com falha seja identificado e isolado para salvar os segmentos posteriores.
7. Como operador, quero reiniciar a Cola e recuperar o último bloco em trânsito para manter o histórico.
8. Como mantenedor, quero confirmar a identidade do processo antigo antes de encerrá-lo para preservar outras gravações.

## Decisões de implementação

- Executar a Cola como serviço Python separado, com FFmpeg para gravar e concatenar. A interface Tauri acompanha o estado pelo motor. O fechamento da janela permite que a gravação prossiga pelo supervisor.
- Manter `-c copy` na melhor qualidade da fonte (`1080p60`) e janelas com sobreposição, ajustando `bloco_min`/`sobreposicao_min` conforme a capacidade medida do motor. Registrar início e fim reais via `segs.csv` e `mtime`.
- Fixar prazo por tentativa de sondagem (`yt_dlp`), gravação (`-rw_timeout`), concatenação (`120 s`) e envio ao motor (`(10, 120) s`). Usar publicação atômica do MP4 (`.parcial`) e estado durável por identidade do bloco (`bloco_id:{canal}:{stem}`).
- Remover bloco e sidecar de chat só após confirmar e persistir `job_id` (ou `already_processed`). Isolar respostas inconclusivas e segmentos `.ts` corrompidos em `corrompidos/`.
- Contabilizar uso de disco por categoria (`segmentos`, `blocos`, `rejeitados`, `corrompidos`, `chats`, `logs`), respeitar `min_livre_gb` + orçamento opcional `max_disco_gb` e rotacionar `ffmpeg.log` em `10 MiB`.
- Reconhecer processos antigos pelo PID, nome `ffmpeg` e `create_time` gravado em `ffmpeg.pid`.
- Validar domínios Twitch/Kick com fronteira exata (`_host_matches`), respeitar `429` da Twitch Helix com `Ratelimit-Reset` sem derrubar gravações ativas, paginar `Helix.live` e renovar `game_ids` por TTL (`300 s` se faltar categoria configurada, `1800 s` completo).

## Decisões de teste

- Costura principal: Cola, motor simulado (`fake_http`) e pequenos arquivos MPEG-TS. Simular fila cheia, timeout, confirmação perdida, processo bloqueado, segmento corrompido não vazio, PID reutilizado, `429` com `Ratelimit-Reset`, orçamento de disco, fallback sem `chat` e chat IRC via `socketpair`.
- Provar recuperação após interrupção antes e depois da confirmação. Medir se uma origem saudável continua produzindo durante a falha simulada.
- Reaproveitar e ampliar os testes de concatenação, rejeitados, sobreposição, disco, Helix e entrega em `cola/tests/`.

## Fora do escopo

Redundância distribuída de gravadores, download retrospectivo de lives sem gravação ou VOD e leitura ao vivo do chat da Kick (apenas documentada abaixo nesta etapa).

## Medição de codecs e disco (16/11/2026)

Medição real sobre **305 s** da live pública `twitch.tv/move_mind` (GTA V, `1920x1080@60`, `h264`, `~7,71 Mbps`) em RTX 3060, comparando cópia direta da fonte, variante `720p60` e recodificações NVENC (FFmpeg 8.0.1). Confirmado via FFmpeg que `av1_nvenc` **não existe** na RTX 3060 (`No capable devices found`).

| Opção | Codec / Preset | Taxa medida | Tempo encode / concat (305 s) | CPU FFmpeg | GPU / NVENC / VRAM (`nvidia-smi`) | SSIM vs fonte | VMAF vs fonte | Observação crítica |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Cópia fonte (`best`, escolhida)** | `h264` `-c copy` (`1080p60`) | **3,23 GiB/h** (293,85 MB; 7706 kbps) | **0,96 s** concat ocioso (66,15 s sob carga VMAF+Whisper) | **1,2%** de 1 núcleo | 0% / 0% / 0 MiB extra | **1,0000** | **100,0** | Preserva 608×1080 no recorte 9:16 |
| **Cópia `720p60`** | `h264` `-c copy` (`720p60`) | **1,42 GiB/h** (129,44 MB; 3395 kbps) | — | **0,9%** de 1 núcleo | 0% / 0% / 0 MiB extra | 0,9774 (full) / **0,9722** (9:16) | 85,41 (full) / **73,24** (9:16) | Recorte 9:16 cai para ~405×720 antes do upscale 1080×1920 |
| **`h264_nvenc`** | `-preset p4 -rc vbr -cq 24` | **2,80 GiB/h** (254,87 MB; 6684 kbps) | 43,59 s (~7,0×) | **82,2%** (1 núcleo eq.) | 32,2% / **98,3%** (pico 100%) / 2033 MiB | 0,9822 | 87,81 | Economiza só ~13% e disputa NVENC/CPU com Whisper e render |
| **`hevc_nvenc`** | `-preset p4 -rc vbr -cq 25` | **2,28 GiB/h** (207,60 MB; 5444 kbps) | 101,54 s (~3,0×) | 38,1% | 27,1% / **47,8%** (pico 100%) / 4390 MiB* | 0,9817 | 87,45 | **Motor recodifica HEVC para H.264** antes do pipeline |
| **`av1_nvenc`** | — | — | — | — | — | — | — | Indisponível na RTX 3060 (requer Ada/RTX 40+) |

\*Pico de VRAM durante `hevc_nvenc` incluiu processo concorrente do motor. Conferido em `clips-kitty/video/encoding.py` (`SLOW_SOURCE_CODECS = ("av1", "vp9", "hevc")`) e `core/pipeline.py` (`convert_slow_source`): o motor converte HEVC de volta para H.264 no disco antes da análise e renderização.

**Decisão:** manter `-c copy` na melhor qualidade da fonte (`1080p60`).

### Espaço no D: e orçamento de disco (R08 lado Cola)

Com **~100–103 GiB livres** no `D:` e guarda de **20 GiB** (`min_livre_gb = 20`), restam **~80 GiB úteis** para captura:

- **Regime normal (motor consumindo):** `Gravador._send_blocks` apaga o `.mp4` e o sidecar de chat imediatamente após confirmação do `job_id` (o motor já copiou o arquivo para `data/downloads/` dentro do `POST /videos/local`), e `entrega.tick` chama `DELETE /videos/{id}` após exportar os cortes. Em disco ficam apenas ~2–5 min de segmentos ativos por canal (~110–300 MB/live).
- **Regime de acúmulo (motor parado ou fila cheia):** considerando `3,23 GiB/h` líquido ou **4,04 GiB/h** com +25% de sobreposição (`4+1 min`):
  - **1 live:** ~24,8 h (líquido) / **~19,8 h** (blocos acumulados);
  - **2 lives:** ~12,4 h / **~9,9 h**;
  - **3 lives:** ~8,3 h / **~6,6 h**.
- **Proteções implementadas:** `Gravador.disk_usage_report()` separa `segmentos`, `blocos`, `rejeitados`, `corrompidos`, `chats` e `logs`; parâmetro opcional `max_disco_gb` pausa novas gravações junto com `min_livre_gb`; `_rotate_log()` rotaciona `ffmpeg.log` ao atingir `10 MiB` (`.1`).

## Chat ao vivo da Twitch e contrato com o motor

- **Módulo stdlib (`cola/cola/chat_ao_vivo.py`):** conecta anonimamente (`justinfan<n>`) via TLS em `irc.chat.twitch.tv:6697` com `CAP REQ :twitch.tv/tags twitch.tv/commands`, um socket/thread por canal gravado, resposta a `PING`/`PONG`, keepalive ocioso (`90 s`) e reconexão exponencial (`1 s` até `30 s`). Armazena `recv_t` (relógio da máquina) e tags IRCv3 (`tmi-sent-ts`, `emotes`, `badges`, `display-name`) em janela de memória limitada (até `50 000` msgs / `2 h`). Ver [12-leitura-de-chat](../06-Integracoes/12-leitura-de-chat.md).
- **Sincronização vídeo × chat (`≤ 2 s`):** `_start()` passa `-segment_list <canal>/segs.csv -segment_list_type csv -segment_list_flags +live` ao FFmpeg. `block_window()` soma as durações exatas do `segs.csv` e ancora o fim no `mtime` do último `.ts` (`inicio = end_t - sum(duracoes)`). Em captura real de 5 min (`move_mind`), a diferença em relação ao início real do 1º segmento foi **1,50 s** e **250 de 251** mensagens capturadas encaixaram na janela `[0, 300 s]` (`t` entre `3,15 s` e `299,17 s`, total de `299` emotes nativos).
- **Contrato `POST /videos/local`:** o lado Cola guarda o snapshot em `<canal>/chats/<stem>.json` (fora de `blocos/`) e envia em `kitty.submit_file(..., chat=...)` como lista ordenada por `t` (`{"t": float, "user": str, "text": str, "emotes": int}`, bruto sem desconto de atraso de reação). Se o motor ainda recusar `chat` (`422` ou `400` citando `chat`), `submit_file` reenvia automaticamente sem o campo. O arquivo de chat é apagado junto com o `.mp4` após confirmação ou movimentação para `rejeitados/`.
- **Kick (somente documentação nesta etapa):** o legado Pusher (`wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679`, canal `chatrooms.{chatroom_id}.v2`) foi descontinuado pela Kick em outubro/2026 (erro `4001`). O transporte atual usa **Centrifugo**: obter token/endpoint via `POST https://web.kick.com/api/v1/realtime/channels/{channel_id}/chat/connection` e `POST https://web.kick.com/api/v1/realtime/auth/connection`, conectar no WebSocket `wss://realtime.*.platform.kick.com/connection/websocket`, assinar `chatrooms.{chatroom_id}.v2` e ler eventos `App\Events\ChatMessageEvent`.

## Achados R04, R06 e R07 fechados na Cola

- **R04:** `ffmpeg` concat limitado a `120 s` (limpando `.parcial` e `.txt` em falha/timeout); `yt_dlp -g` com `timeout=30 s`; `_kick_live` com `socket_timeout=15 s`; `ffmpeg` de captura com `-rw_timeout 15000000` (15 s); `kitty.submit_file` com timeout `(10, 120) s` em vez de `600 s`. *(Obs.: a separação assíncrona das etapas dentro do laço `cola/__main__.py` ficou fora dos arquivos deste cartão.)*
- **R06:** ID estável `bloco_id:{canal}:{stem}` gravado em `estado.mark_sent` evita reenvio se sobrar arquivo; recuperação de resposta perdida via `job_for_video` sem duplicar job; `_quarantine_bad_segments` valida com `ffprobe` e move `.ts` corrompidos não vazios para `corrompidos/` desbloqueando o canal; `ffmpeg.pid` grava `pid:create_time` e `kill_orphans()` confere nome e `create_time` (±2 s) antes de encerrar, além de limpar `.parcial`/`.txt` órfãos.
- **R07:** `_host_matches()` valida fronteira de domínio (`urlsplit().hostname`, rejeitando `eviltwitch.tv` e `twitch.tv.evil.com`); `Helix` trata HTTP `429` lendo `Ratelimit-Reset` / `Retry-After` (`TwitchRateLimited`) e pula chamadas HTTP até o horário de retomada sem falhar o tique nem parar gravações em andamento; `_game_ids` renova por TTL (`300 s` se faltar alguma categoria como GTA VI, `1800 s` completo); `Helix.live()` pagina cursor `after` e divide em lotes de 100. `cola/config.toml` permanece com `canais = []`.

## Ensaio ao vivo e recomendação de bloco (16/11/2026)

Ensaio isolado em `D:\clipador-gta6\cache\ensaio-gravacao\ao_vivo` (`bloco_min=4`, `sobreposicao_min=1`, canal real `twitch.tv/move_mind`, idioma `pt`, com chat IRC ativo e reconexão automática após `gaierror` inicial em 1 s), enviando **2 blocos** ao motor vivo `127.0.0.1:8765`:

| Fase | Bloco 1 (Job 92) | Bloco 2 (Job 93) |
| --- | --- | --- |
| Gravação até fechar 5 segmentos (`4+1 min`) | ~5 min 10 s (`21:08:32 → 21:13:42` incl. envio) | ~4 min de passo após bloco 1 (`21:12:27 → 21:17:28` segs) |
| Concat (`_concat`) | — | 66,15 s *(sob carga concorrente de VMAF+Whisper; ocioso = 0,96 s)* |
| Envio (`POST /videos/local` c/ fallback/aceite 200) | — | 9,00 s (`21:20:11`) |
| Espera na fila | 0 s (`21:13:42 → 21:13:42`) | **157 s (2,6 min)** (`21:20:11 → 21:22:48`) |
| Processamento no motor (Whisper + PANNs + Luna + render) | **545 s (9,1 min)** (`21:13:42 → 21:22:47`, 1 corte) | **611 s (10,2 min)** (`21:22:48 → 21:32:59`, 2 cortes) |
| Entrega (`entrega.tick` → `saida/pendentes/`) | < 1 s (`21:22:47`, `#167`) | < 1 s (`21:32:59`, `#168` e `#169`) |
| **Latência total (início do bloco → corte pronto)** | **14 min 15 s** (9 min 16 s após fechar o bloco) | **20 min 32 s** (15 min 31 s após fechar o bloco) |

**Recomendação de `bloco_min` / `sobreposicao_min`:** com o motor atual rodando Whisper `beam_size=5 + VAD 0.3` + PANNs + Luna em um único trabalhador (~**9 min** por bloco de 5 min), o ritmo `4+1 min` (15 blocos/h por live = 1 bloco a cada 4 min) **estoura a fila continuamente** (> 2× mais lento que o tempo real, mesmo com apenas 1 live) e consome ~15 chamadas/h ao Luna por canal. Para operar ao vivo em "postar na hora" sem acumular fila nem queimar cota do ChatGPT:
- **Se mantiver o motor com `beam_size=5`:** usar **`bloco_min = 9`, `sobreposicao_min = 1`** (passo de 9 min, ~6,7 chamadas Luna/h) ou **`bloco_min = 10`, `sobreposicao_min = 1`** com **no máximo 1 live gravada por vez** — ou processar só momentos de pico pelo garimpeiro/chat quando ligar 2–3 lives.
- **Para 2–3 lives simultâneas em blocos curtos (`4+1` ou `5+1`):** exige reduzir o tempo de transcrição por bloco longo no motor (ex.: `beam_size=1` para blocos > 60 s, conforme já apontado na [spec 05](../03-Producao-de-clips/05-ia-e-transcricao.md), que corta Whisper ~2×) e/ou filtrar blocos sem pico de chat/áudio antes de chamar o Luna.

## Testes executados

Suíte completa da Cola em `D:\clipador-gta6\cola` (`pytest -p no:cacheprovider -q`): **100 aprovados** (cobrindo `test_gravador.py`, `test_kitty.py`, `test_twitch.py`, `test_chat_ao_vivo.py`, `test_garimpeiro.py`, `test_entrega.py`, `test_estado.py`, `test_config.py`), incluindo os novos testes para IRC/tags/reconexão, janela de chat (`segs.csv` + `mtime`), fallback do `submit_file`, R04 timeouts, R06 quarentena/PID `create_time`/ID estável, R07 domínio/`429` `Ratelimit-Reset`/TTL de categorias e R08 orçamento de disco.

## Notas

Relaciona-se aos achados **R04, R06, R07 e R08** em [rev-code-review](../90-Auditorias/rev-code-review.md). Pasta temporária de ensaio (`D:\clipador-gta6\cache\ensaio-gravacao`) removida após extração das métricas.

