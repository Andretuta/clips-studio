# Transcrição, Luna e seleção de cortes

Estado `ready-for-agent`. Prioridade P1.

A análise visual em lotes foi implementada e testada. O próximo ensaio mede o fluxo com transcrição e renderização em um bloco real.

## Problema

A transcrição e a seleção passam pelo mesmo trabalhador de vídeo. Uma sessão expirada, limitação do plano ou inferência lenta pode deixar origens prontas sem cortes. Desde 16/11 (R09, Cola `66cced8`) a Cola reconhece pela mensagem do erro login, limite, crédito ou chave da IA e tenta de novo a cada 30 min sem gastar tentativa nem apagar a fonte. As outras falhas ainda usam o mesmo intervalo, e o horário de retomada informado pelo ChatGPT ainda não é usado.

## Solução

Persistir etapas reaproveitáveis, relatar a causa de espera e retomar o processamento quando o recurso estiver disponível.

## Histórias de usuário

1. Como operador, quero testar a transcrição com os pesos já disponíveis para validar o PC antes de gravar.
2. Como operador, quero ver se o erro é login, limite, indisponibilidade ou modelo para saber o próximo passo.
3. Como operador, quero guardar blocos e transcrições enquanto espero o plano liberar para evitar perder momentos da live.
4. Como editor, quero receber trechos selecionados pelo Luna com tempo e contexto para confirmar o que vai à Mesa.
5. Como editor, quero revisar a legenda em português e o texto de publicação antes de aprovar para melhorar a exatidão.
6. Como operador, quero escolher se aceito transcrição mais lenta na CPU para controlar a latência da estreia.
7. Como mantenedor, quero repetir apenas uma etapa que falhou para poupar tempo e uso do plano.
8. Como mantenedor, quero medir tempo e memória por etapa para escolher as próximas otimizações a partir do custo observado.

## Decisões de implementação

- Manter Whisper local para texto e Luna para seleção e metadados quando o plano estiver disponível. Preservar intervalos e identidade do candidato no resultado estruturado.
- O motor Python usa faster-whisper com CTranslate2 e aceleração CUDA quando disponível. O FFmpeg entrega quadros amostrados para a análise visual. Reduzir os quadros a sinais de movimento, corte e brilho em lotes, preservando a diferença entre quadros na fronteira dos lotes.
- Medir cada etapa com as mesmas entradas e configurações. Uma eventual rotina Rust deve ser independente da janela, consumir dados definidos pelo motor e passar na comparação de memória, tempo e equivalência de saída antes de substituir a rotina atual.
- Validar modelo, pesos locais e dependências CUDA no ensaio. Informar quando o processamento usar CPU, cache ou download. Validar cache pela identidade da fonte e opções de transcrição.
- Aplicar prazos e cancelamento a chamadas externas. Classificar falhas transitórias, quota com data, login e entrada inválida. Pausar e retomar no instante apropriado à classificação.
- Definir a política de automação do ChatGPT para o caminho agendado e para o ingresso da Cola. Respeitar limites do plano e qualquer troca de provedor autorizada.
  - **Conferido no código em 16/11, 18h40.** A autorização de automação só é exigida quando o job chega com `origin` igual a `watch` ou `stream` (`server/jobs.py`, `_check_plan`; a recusa está em `llm/signin/chatgpt.py`, `check_job`). Esse campo só é definido por `server/automation.py` (canais vigiados) e `server/integrations.py`. O garimpeiro da Cola posta em `/jobs` sem `origin` (`cola/kitty.py`, `submit_url`), então a chave desligada **não bloqueia a estreia**. Contrapartida: os jobs da Cola rodam sem supervisão mas não se declaram assim, e o consentimento que o app pede para uso desacompanhado do plano não os vê. Isso é decisão de política do usuário, não defeito técnico.
- Tratar título, descrição e chat como dados da fonte. O texto da análise pode recomendar cortes. Publicar ou alterar a operação exige ação apropriada em etapa própria.

## Decisões de teste

- Costura principal: tarefa de processamento com transcrição curta e provedor substituível. Verificar respostas objetivas, atraso, timeout, quota, logout e retomada sem nova transcrição.
- Ensaiar áudio PT offline com GPU e conferir o caminho de degradação em CPU. Verificar qualidade e latência com uma gravação autorizada curta.
- Reaproveitar testes de sign-in, seleção de candidatos, repetição de transcrição, checks do motor e caches.
- Manter o teste de quadros repartidos entre lotes e comparar os sinais com a referência. Medir transcrição fria, transcrição com cache, análise visual e renderização com um bloco real de cinco minutos. Registrar RAM, VRAM e tempo de cada etapa.

## Fora do escopo

Trocar de plano automaticamente, acionar créditos sem escolha do operador e fazer o Luna controlar a publicação.

## Notas

O status do plano e o status do assistente interno são contratos distintos. A métrica principal é tempo até o primeiro corte revisável. O ensaio sintético da análise visual mediu 333 para 38 MiB de pico de RAM e 3,48 para 1,61 s de tempo mediano, com sinais idênticos. Relaciona-se ao achado R09.

### Correção do corte precoce no Whisper — clipe 158 (16/11/2026)

Commit: `clips-kitty` `35a226b`.

- **Causa raiz:** o `faster_whisper` concatena os trechos do Silero VAD em janelas de até 30 s. Com `vad_filter=True` (limiar padrão `0.5`) e decodificação gulosa (`beam_size=1`), o `large-v3-turbo` emitiu `<|4.46|><|endoftext|>` logo após `"action"`, disparando `single_timestamp_ending` (`seek += segment_size`), que descartou os 21 s restantes da janela apesar da fala contínua em inglês (conferida nos quadros do vídeo aos 10 s, 13 s, 15 s, 19,5 s e 24,5 s). Ajustar apenas limiares de probabilidade/silêncio ou apenas o limiar do VAD não impediu o encerramento precoce com `beam_size=1`.
- **Correção (`transcription/transcriber.py`, `_run`):** passou a usar `vad_parameters={"threshold": 0.3}` e `beam_size=5 if _on_gpu(model) else 2`. Teste de regressão `test_whisper_run_avoids_greedy_early_stop_and_strict_vad` adicionado em `tests/test_transcript_repair.py`.
- **Medições com cópias reais em `D:\clipador-gta6\cache\ensaio-hydrogen` (GPU CUDA, `large-v3-turbo`):**
  - **Clipe 158 (`25,5 s`):** subiu de **1 trecho até 4,4 s** para **16 trechos até 25,20 s** (`[0.00–4.44]` até `[24.52–25.20]`, capturando `"Fix the food"`, `"Fix everything"`, `"We're gonna die"`, `"Oh, my God"`).
  - **Clipe 159 (`28 s`):** **8 trechos até 27,42 s** (sem regressão; desfez o trecho antigo fundido `9,3–19,2 s` em `[18.05–19.19]`).
  - **Silêncio sintético (`silence_20s.wav`, 20 s):** **0 trechos** (`0.00 s`), sem alucinação.
  - **Mix de 150 s na GPU:** **4,41 s** (`beam_size=5`, VAD `0.3`, 218 palavras) contra **4,48 s** (`beam_size=1`, VAD `0.5`, 127 palavras).
- **Testes:** `test_transcript_repair.py`, `test_whisper_gpu_libraries.py` e `test_cancel.py` passaram (**29 aprovados**). O motor vivo (`127.0.0.1:8765`) continua com o código anterior até ser recarregado pelo operador.
- **Revisão do Claude (16/11, 20h20).** Mesmo modelo e mesma GPU (RTX 3060), comparando as configurações direto no `model.transcribe`:

  | Configuração | Clipe 158 (25,5 s) | Clipe 159 (28 s) | Silêncio 20 s | Bloco real de 5 min (`local_afe4d6ad5172`, primeiros 300 s) |
  | --- | --- | --- | --- | --- |
  | A · beam 1, VAD 0,5 (antes) | até 4,5 s, 9 palavras | até 27,4 s, 41 | 0 | 7,2 s, 91 trechos, 462 palavras |
  | B · beam 1, VAD 0,3 | até 20,7 s, 22 | até 27,4 s, 41 | 0 | 7,6 s, 89, 443 |
  | C · beam 5, VAD 0,3 (adotada) | até 25,2 s, 58 | até 27,4 s, 41 | 0 | 14,1 s, 71, 397 |
  | D · beam 5, VAD 0,5 | até 25,2 s, 33 | até 27,4 s, 42 | 0 | 10,6 s, 65, 454 |

  - **Decisão:** fica a C. A fonte da estreia são clipes curtos da Twitch, e nos clipes ela é a que mais recupera fala.
  - **Custo num bloco longo:** cerca de 2× o tempo e 14% menos palavras que antes.
  - **Instabilidade:** em duas rodadas seguidas, a C deu 54 e 69 trechos no mesmo bloco, porque o *fallback* de temperatura introduz amostragem. A A deu o mesmo resultado nas duas.
  - **Comentário do código:** dizia que o beam 5 "tem a velocidade do beam 1" e foi corrigido com os números medidos. Se os blocos longos voltarem a ser fonte, separar a configuração por duração.

### Chat do bloco local, `momento_chave` e Whisper por duração (16/11/2026, ~22h02)

Commit: `clips-kitty` `5ba4541` (aguarda recarga do processo vivo em `127.0.0.1:8765`).

- **Chat do bloco local (`server/api.py`, `core/pipeline.py`, `core/housekeeping.py`):**
  - `POST /videos/local` (`LocalVideoIn`) passou a aceitar o campo opcional `chat`: lista ordenada de `{"t": float, "user": str, "text": str, "emotes": int?}`, persistida em `data/chats/{video_id}.json` (limpa em `DELETE /videos/{video_id}` e no bucket `"orphan_chats"` da limpeza periódica).
  - Para vídeos `local:`/`local_*`, `_fetch_hype` carrega o chat local salvo em disco em vez de buscar chat remoto de VOD; sem `chat`, o comportamento é idêntico ao anterior.
  - **Atraso (`chat_live_lag_seconds: 3` em `config/gaming.yaml`):** configurável e menor que o `6.0 s` do replay de VOD porque o `t` do gravador já chega no relógio local do espectador (atraso apenas de reação humana para digitar no chat, sem compensação extra de latência da transmissão).
- **Pontuação `momento_chave` (`analysis/chat_moments.py`, `analysis/fusion.py`, `server/api.py`):**
  - Detector passa a usar linha de base adaptativa ao volume do chat, razão de usuários únicos (`unique_ratio` para resistir a spam/copypasta), rajadas de emotes (`emotes`) e léxico PT/EN (`kkkk`, `clipa`, `?????`, `W`/`L`, `KEKW`, `LUL`, `OMEGALUL`, `Pog`, etc.), além da fusão com áudio e sinais do streamer.
  - Cada corte expõe `momento_chave: {"score": 0..1, "motivos": [...]}` no resultado interno e no campo de nível superior de `/videos/{video_id}/clips` para consumo da regra de auto-postagem.
  - **Avaliação reproduzível com dados reais (`scripts/eval_chat_moments.py` + `tests/fixtures/twitch_gta_chat_moments.json`, sem credenciais — 15 VODs reais de GTA V/RP e 64 clipes populares como verdade-base):**
    - Ajuste (`tune`, 8 VODs, 37 clipes): `precision=0,2148`, `recall_all=0,6757`, `F1=0,3260`, `recall@5=0,1892`, `recall@10=0,3243`, `recall@15=0,5676`, erro absoluto mediano `14,25 s` (`offset_to_mid=-6,85 s`).
    - Validação separada (`val`, 7 VODs, 27 clipes): `precision=0,0862`, `recall_all=0,3704`, `F1=0,1399`, `recall@5=0,0370`, `recall@10=0,2222`, `recall@15=0,3704`, erro absoluto mediano `26,10 s`.
    - Consolidado (`all`, 15 VODs, 64 clipes): `precision=0,1554`, `recall_all=0,5469`, `F1=0,2420`, `recall@5=0,1250`, `recall@10=0,2812`, `recall@15=0,4844`, erro absoluto mediano `15,00 s`.
- **Whisper separado por duração (`transcription/transcriber.py`, `LONG_BLOCK_SECONDS = 120.0`):**
  - `_video_duration()` decide o perfil em `_run()`: mídia curta (`< 120 s` ou duração desconhecida) mantém `beam_size=5` na GPU (`2` na CPU) e VAD `0,3`; blocos longos (`>= 120 s`) usam `beam_size=1`, VAD `0,5` e `temperature=0.0` (sem fallback de amostragem, determinístico entre rodadas).
  - **Medições reais na RTX 3060 (`large-v3-turbo`):**
    - Clipes curtos (`ensaio-hydrogen`): `clip158` (`25,5 s`) preservado com `5,01 s`, 58 palavras até `25,2 s` (vs `0,87 s` / 9 palavras no beam 1); `clip159` (`28 s`): 8 trechos, 41 palavras até `27,4 s`; `silence_20s`: 0 trechos.
    - Bloco real de 5 min (`bloco_5min.mp4`, `300 s`): `beam5_vad03_defaultT` = `169,98 s` / `56,37 s` (instável, 391/340 palavras); `beam5_vad03_T0` = `17,02 s` / `16,72 s` (586 palavras); `beam2_vad03_T0` = `14,92 s` / `17,75 s` (429 palavras); **`beam1_vad05_T0` (adotada para `>= 120 s`) = `7,57 s` / `7,73 s` idênticos nas duas rodadas (91 trechos, 454 palavras)**.
- **Ensaio E2E isolado de bloco real de 5 min na porta `8766` (16/11, ~21h58–22h01 BRT):**
  - Entrada: bloco H.264 de `300 s` + 173 mensagens de chat sintético PT/EN (3 rajadas), `gaming_scoring: true`, `chatgpt/gpt-6-luna`, `large-v3-turbo` CUDA, YOLOv8 CUDA, `parallel_renders: 3`.
  - **Tempos por etapa:** upload (`POST /videos/local`) **1,33 s**; `[1/4]` + carga fria de modelos/PANNs + Whisper `[2/4]` **47,17 s** (`~30 s` de carga fria de modelos; decodificação Whisper **16,90 s**, 91 trechos); `[3/4]` análise multimodal + seleção Luna + scoring + ranking **73,45 s** (sinais/OCR `30,00 s`, Luna chunk `12,75 s`, score 14 janelas + fusão `24,81 s`, ranking 4 finalistas `5,89 s`); `[4/4]` metadados Luna (`~8,9 s`) + tracking GPU e render de 4 clipes (`~112,6 s`) **121,55 s**. Total no worker: **249,09 s (~4,15 min)** (antes 9–10 min), produzindo 4 cortes com `momento_chave` (`0,69`–`0,86`).
  - **Recursos e limite:** pico de VRAM **4.666,0 MiB** (de 12 GiB na RTX 3060) e pico de RAM do sistema de **99,5%** durante os 3 renders paralelos + CUDA — recomenda-se acompanhar RAM ou considerar `parallel_renders: 2` se houver outras tarefas pesadas concorrentes.


### Revisão do Claude sobre o cartão [Motor] (16/11, 22h20)

**Whisper em blocos longos (clips-kitty `bbad90d`).** Mesmo bloco real de 5 min, RTX 3060, `temperature=0`, duas rodadas cada:

| Configuração | Tempo | Trechos | Palavras | Fala coberta | Buracos > 15 s | Maior repetição |
| --- | --- | --- | --- | --- | --- | --- |
| beam 1, VAD 0,5 (Hydrogen) | 11,9 s / 7,2 s | 91 | 462 | 122,7 s | 3 | 2 |
| **beam 5, VAD 0,3 (adotada)** | 13,7 s / 13,9 s | 53 | 586 | 160,8 s | 2 | 1 |
| beam 5, VAD 0,5 | 9,7 s / 9,6 s | 68 | 435 | 136,4 s | 4 | 14 |

- **O que causava a lentidão:** o fallback de temperatura (56 a 170 s), não o beam.
- **A adotada:** pega 27% mais palavras e 31% mais fala, sem repetição e igual nas duas rodadas.
- **Custo:** 6,6 s a mais num trabalho de cerca de 249 s por bloco.
- **O que não mudou:** a regra dos clipes curtos. Só os blocos `>= 120 s` desligam o fallback.
- **Testes:** `test_transcript_repair.py` e `test_whisper_gpu_libraries.py` passaram.

**Detector de chat (clips-kitty `bbc31fd`).** A rodada do motor ajustou o detector olhando os dois conjuntos, e no conjunto de validação ele piorou. Comparação com o mesmo script (`scripts/eval_chat_moments.py`) e o mesmo fixture (15 VODs, 64 clipes):

| Validação (7 VODs, 27 clipes) | F1 | Precisão | recall@5 | recall@10 | recall@15 | Erro mediano |
| --- | --- | --- | --- | --- | --- | --- |
| Detector antigo (`5ba4541~1`) | 0,148 | 0,092 | 0,074 | 0,185 | 0,333 | 12,4 s |
| Rodada do motor (`5ba4541`) | 0,140 | 0,086 | 0,037 | 0,222 | 0,370 | 26,1 s |
| **Corrigido (`bbc31fd`)** | **0,163** | **0,100** | **0,111** | **0,296** | **0,407** | 25,6 s |

- **Como se escolheu:** grade de 16 combinações (BASELINE 45/180, folga 0/15 s, junção 10/15 s, razão de únicos 0/0,55), escolhida pelo conjunto de ajuste (F1 0,326, recall@10 0,378).
- **A folga de 15 s antes da rajada** piorava a validação em todas as combinações e saiu.
- **A junção de rajadas** voltou a 10 s.
- **A razão de usuários únicos** não muda nada neste fixture: os autores vêm com hash e quase não se repetem. Fica pela proteção contra spam em chat ao vivo.
- **Testes:** chat, hype, fusão, gaming e upload local: **186 aprovados**.
- **Limitações:**
  - **Erro de tempo:** continua o dobro do antigo (o evento sai cerca de 14 s antes do meio do clipe na validação). Investigar antes de dar peso alto ao chat na posição do corte.
  - **Fixture curto:** com 27 clipes de validação, a diferença entre as linhas é pequena e pode ser ruído.
  - **Regime diferente:** o fixture usa janelas de cerca de 50 min de VOD. O bloco ao vivo tem 5 min, então a base de 180 s fica truncada nos primeiros 3 min de cada bloco. Levar a base de um bloco para o próximo fica para depois.

**RAM.** O ensaio chegou a 99,5% de RAM (15,9 GiB na máquina) com `parallel_renders: 3`. Com Cola gravando e Electron aberto ao mesmo tempo, a recomendação é `parallel_renders: 2` no `config/settings.yaml` local (não versionado).

### VRAM por etapa (Claude, 17/11, 04h09)

RTX 3060, 12.288 MiB. Cada etapa rodou num processo próprio, com CUDA limpo, enquanto outro processo lia a memória usada da placa pelo NVML a cada 50 ms. A tabela mostra o pico de cada etapa acima do que o Windows já ocupa: ~1,5–2,0 GiB com a área de trabalho. Por processo, o `nvidia-smi` mostra N/A no WDDM. Material: 5 min do VOD `local_afe4d6ad5172.mp4` a partir de 300 s e um clipe da Twitch de 24 s. Scripts no scratchpad da sessão (`bench/vram.py`, `bench/residente.py`).

| Etapa | VRAM acima da base | Tempo |
|---|---|---|
| Whisper large-v3-turbo fp16, bloco de 5 min | +2.531 MiB | 44,6 s (273 palavras) |
| PANNs (sons do jogo) sozinho | +357 MiB | 18,9 s |
| Whisper + PANNs em paralelo, como o motor faz | +2.485 MiB | 34,9 s |
| 1 render (NVDEC + NVENC + libass) | +393 MiB | 33,9 s |
| 3 renders em paralelo (`parallel_renders: 3`) | +1.177 MiB | 46 s |
| Passo gamer de um corte (YOLO pose acha a webcam + cabeça + render, layout `half`) | +582 MiB | 72,9 s |
| Residente: YOLO pose + PANNs carregados e parados | +244 MiB | — |

- O Whisper é carregado a cada transcrição e solto no fim. O YOLO (`video/tracker.py`) e o PANNs ficam em cache no processo do motor. Por isso o motor parado segura ~0,25 GiB.
- O pico real do motor é o Whisper, ~2,5 GiB. Se 3 renders caírem junto com uma transcrição, a soma fica perto de 4 GiB. O ensaio E2E de 16/11 bateu 4.666 MiB absolutos (com a área de trabalho). A placa fica com ~6 GiB livres, então a VRAM não é o gargalo. O limite é a RAM (99,5% com 3 renders, ver acima).
- O TalkNet (`video/asd.py`) não roda: os pesos não estão instalados. O modelo onnx de turnos de voz também não está. O OCR (RapidOCR onnx) está disponível.

### Desempenho com a VRAM livre (Claude, Codex e Antigravity, 17/11)

O usuário pediu para usar os ~6 GiB livres da placa. Foram cinco cartões. Claude ficou com o Whisper e o OCR; o YOLO foi para o Codex e o render na GPU para o Antigravity (Gemini 4 Hydrogen). Os scripts de medição estão em `D:\clipador-gta6\cache\ensaio-vram\claude\`.

**1. Whisper fica carregado entre blocos (`312bec4`).** `transcribe()` guarda o modelo da GPU depois de uma transcrição que deu certo, e o próximo bloco o reaproveita.
- **Tempo:** a 1ª transcrição do `bloco5.mp4` leva o custo da carga. A 2ª e a 3ª levaram 9,9 s e 11,8 s, a mesma 273 palavras.
- **Custo:** ~2,1 GiB fixos de VRAM.
- **O que não fica guardado:** um modelo que falhou (é recarregado) e o modelo de CPU (a RAM é o recurso escasso).
- **Teste:** `test_a_gpu_model_that_worked_stays_loaded_for_the_next_job`; 31 testes de Whisper, cancelamento e reparo verdes.

**2. Whisper em lote: descartado para a estreia.** `BatchedInferencePipeline` (faster-whisper 1.2.1) no mesmo bloco, com beam 5, VAD 0,3, temperatura 0 e lote 8:

| Variação | Tempo | Palavras (atual: 273) | Semelhança com o atual |
|---|---|---|---|
| Padrão | 6,1 s | 114 | 0,42 |
| Com timestamps | 33,7 s | 300 | 0,51 |
| Com timestamps, beam 1 | 5,0 s | 278 | 0,44 |
| VAD 0,5 | 9,1 s | 292 | 0,58 |

O texto muda demais, e não há gabarito para saber qual erra mais. O ganho seria ~5 s por bloco, contra o risco de refazer a calibração do clipe 158.

**3. OCR na GPU pelo DirectML (`46f03fb`).**
- **Código:** `analysis/game_text._new_engine()` usa `det/cls/rec_use_dml` quando o onnxruntime instalado tem `DmlExecutionProvider`. Com o build comum nada muda, e um DirectML que não inicia volta para a CPU.
- **Medido:** nos mesmos 20 quadros do bloco, com o recorte e a largura do `game_text`, foram **0,93 s por quadro na CPU e 0,20 s no DirectML** (mediana de 3 rodadas), com o texto lido idêntico. No bloco, o OCR cai de ~30 s para ~6 s.
- **Compatibilidade:** o VAD Silero do Whisper deu os mesmos trechos com onnxruntime 1.32 e onnxruntime-directml 1.24.4. As transcrições curtas variam entre execuções em qualquer versão, porque abaixo de 120 s o fallback de temperatura é aleatório. As suítes `test_game_text`, `test_voice_turns`, `test_basketball_screen` e `test_whisper_gpu_libraries` passam com as duas versões.
- **Ativação (operador, com o motor parado):** as DLLs ficam presas enquanto o motor roda. Na pasta `clips-kitty`, com `UV_CACHE_DIR=D:\clipador-gta6\cache\uv`:
  1. `uv pip uninstall --python .venv\Scripts\python.exe onnxruntime`
  2. `uv pip install --python .venv\Scripts\python.exe onnxruntime-directml==1.24.4`
- **Feito às 09h10 de 17/11** (Claude, a pedido do usuário, fila vazia). Antes de subir o motor: provedores `DmlExecutionProvider` e `CPUExecutionProvider`; o OCR leu "VICTORY ROYALE" num quadro de teste em 3,3 s na primeira vez e 0,08 s depois; o VAD Silero carrega. Os modelos de voz faltavam em `models/`; baixados às 09h20 e conferidos no 1.24.4 (ver a cor do segundo falante na [spec 06](06-editor-e-render.md)).
- **Reinstalação (resolvido às 09h23 de 17/11):** o `requirements.txt` pede `onnxruntime-directml` no Windows e `onnxruntime` fora dele. O `pyproject.toml` ganhou `[tool.uv] override-dependencies`, que tira do Windows o `onnxruntime` comum que o faster-whisper, o Piper e o RapidOCR pedem pelo nome. Medido com o uv 0.11.28: `uv pip compile` dá só `onnxruntime-directml 1.24.4` no Windows e só `onnxruntime 1.32.0` no Linux; `uv pip install --dry-run --reinstall -r requirements.txt` no venv reinstala só o directml (antes punha o 1.32 por cima). Vale para o `uv` rodado na pasta `clips-kitty`. O `pip` não tem essa opção: no Windows ele ainda instalaria os dois. A cópia de teste está em `D:\clipador-gta6\cache\ort-dml`.

**4 e 5.** O YOLO em lote (Codex, aplicado em `67e6aaf`) e os filtros do render em CUDA (Antigravity, `dc9f9cb`) estão na [spec 06](06-editor-e-render.md).
