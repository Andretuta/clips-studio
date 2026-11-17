# Editor, legendas, marca e renderização

Estado `ready-for-agent`. Prioridade P1.

## Problema

O corte precisa manter legibilidade no celular e identidade do canal. Fonte longa, layout variado e mudança de proporção podem alterar a posição das legendas, a marca e a duração percebida.

## Solução

Usar os mesmos contratos de posição, tempo e estilo na prévia e no vídeo final. Manter áudio sincronizado e separar edição de render caro.

## Histórias de usuário

1. Como editor, quero a prévia no mudo ao abrir um corte para controlar o som do ambiente.
2. Como editor, quero legendas discretas e centralizadas com até duas linhas para manter o gameplay visível.
3. Como editor, quero editar e dividir palavras longas e hifenizadas de modo legível para evitar três linhas.
4. Como editor, quero ligar ou desligar a marca CG com @CortesGameroffc por corte para escolher a identidade da postagem.
5. Como editor, quero ajustar tamanho e opacidade e ver a marca percorrer a área real da imagem para evitar que fique restrita às margens.
6. Como editor, quero conferir o resultado na proporção de publicação sem perder o enquadramento após exportar.
7. Como operador, quero recuperar um vídeo se o render falhar para publicar uma versão revisada em seguida.

## Decisões de implementação

- A janela exibe a prévia e envia o pedido de exportação pela API. O motor Python coordena a renderização com FFmpeg e seleciona NVENC quando o meio de codificação e o hardware permitem.
- Obter zonas de legenda e marca a partir das dimensões reais e do layout. Posicionar legenda central dentro da zona que preserva a imagem e limitar a duas linhas tanto na divisão quanto no arquivo renderizado.
- Manter o PNG CG e o texto do perfil como grupo visual. A trajetória pode cruzar zonas internas da área de gameplay, com margens proporcionais e tamanho/opacidade resolvidos de modo consistente.
- Separar o crédito ao streamer da marca do canal. Guardar estilo e indicação de marca já incorporada para reaproveitamento em compilados.
- Reusar a trilha de edição, guardar o original e concluir o MP4 temporário antes de substituir uma mídia. Isolar falta de GPU, falta de espaço e falha de codec.
- Compartilhar as regras com a Mesa e compilação. Relatar progresso e permitir cancelar render pelo motor.

## Decisões de teste

- Costura principal: exportação pelo editor com fontes controladas. Conferir a duração, proporção, trilhas e quadros renderizados em vários tempos.
- Testar duas linhas em fontes longas, ritmo rápido e hifens, e visibilidade da marca em posições internas com tamanho e opacidade distintos.
- Reaproveitar testes de legendas, layout e re-render. Comparar a prévia no mudo com o MP4 final que conserva sua faixa de áudio.
- Verificar a prévia, a escolha de pasta e a exportação no Tauri. Medir tempo, RAM e VRAM do render por perfil, com a mesma mídia, opções e saída esperada em cada execução.

## Fora do escopo

Detecção automática de cada elemento da interface de GTA VI e garantia de impedir edição ou reutilização de uma cópia.

## Notas

Inclui saída vertical para Shorts/TikTok e preservação de aspect ratio para material horizontal.

## Autonomia editorial opt-in — 16/11/2026, Codex

No código atual, `analysis/highlights.py` e seus prompts já selecionam janelas, início/fim, hook, título e hashtags a partir da transcrição e sinais. Fusão/regras ajustam candidatos; Whisper e o construtor de legendas cuidam das palavras/tempos. Enquadramento depende de layout, detecção e render, sem novo comando livre do Luna para zoom. Na Mesa, texto, destinos, marca e aprovação eram manuais; duração/layout eram revistos no editor quando a fonte ainda existia.

`llm/editorial.py` adiciona revisão **desligada por padrão** da cópia pronta: título até 100 caracteres, descrição até 3.000, até 12 hashtags e aparo de no máximo 2 s por borda. Valida formato/números, recusa NaN e mantém tag do jogo. Transcrição temporizada limita aparo às margens fora das falas detectadas com 0,1 s de folga (não comprova silêncio do jogo); sem evidência, não muda bordas. Mantém ao menos 5 s, ou todo corte que já era menor. Não oferece ferramentas nem URLs ao modelo.

`video_editor/desk.py` usa FFmpeg com prazo para o aparo, mantém áudio e conserva original. Aparar vídeo já legendado conserva a sincronia das legendas incorporadas. Marca é aplicada na aprovação se ainda não estava incorporada. Blur sem webcam e polish desligado não mudaram. É respeitada a autorização de automação do plano no banco; falha da IA ou decisão inválida impede seguir para postagem.

Testes de limites, fala, ausência de transcrição e tag em `test_electron_publication.py`; entrega/transcrição em `cola/tests/test_entrega.py`. Números finais e roteiro na [spec 09](../04-Mesa-e-publicacao/09-publicacao-e-contas.md). Não houve avaliação artística com Luna nem medição de render em gameplay real. A revisão é posterior ao pipeline e não exigiu alterar `core/pipeline.py`; emissão de `momento_chave` continua com o agente do motor.

### RAM do render (Claude, 16/11, 22h45)

O ensaio de 5 min do cartão [Motor] chegou a 99,5% de RAM (15,9 GiB na máquina). A medição separou as partes, num trecho de 30 s do bloco real `local_afe4d6ad5172`, com render vertical rastreado (RTX 3060, ffmpeg 8.0.1):

| Processo | Pico de RAM |
| --- | --- |
| Python do render (recorte quadro a quadro) | 62 MiB |
| ffmpeg decodificador (NVDEC, `-hwaccel auto`) | 344 MiB |
| ffmpeg codificador (NVENC), antes | **2.553 MiB** |
| YOLO pose na GPU (runtime CUDA do torch, uma vez por processo) | +1.329 MiB de RAM; 42 MiB de VRAM |

- **Causa:** `-shortest` com `shortest_buf_duration` padrão de 10 s. O ffmpeg guarda até 10 s de quadros crus para alinhar o fim do áudio e do vídeo.
- **Teste das opções, uma por vez, no codificador:**

  | Variante | Pico | Tempo |
  | --- | --- | --- |
  | Sem `-shortest` | 809 MiB | 7,8 s |
  | Com `-shortest_buf_duration 1` | 993 MiB | 7,8 s |
  | Original | 2.578 MiB | 9,7 s |

  Mesmas durações de vídeo e áudio na saída. Loudnorm, `-fps_mode cfr` e `movflags` não mudam nada.
- **Correção (clips-kitty `9773616`):** `-shortest_buf_duration 1` em todo `-shortest` de produção (cropper, compose, compilação, dublagem, encerramento).

| Render real | Antes | Depois |
| --- | --- | --- |
| 1 de 30 s | 2,9 GiB, 21,5 s | **1,36 GiB, 18,5 s** |
| 3 em paralelo | 6,8 GiB, 47,6 s | **3,7 GiB, 37,6 s** |

- **Testes:** render, compilação, sports, remote render, cropper e outro: 214 aprovados. As 12 falhas de `test_outro.py` já estavam no [relatório da suíte completa](../90-Auditorias/suite-completa-2026-11-16.md).
- **Não foi para a VRAM, e por quê:**
  - Decodificação (NVDEC), codificação (NVENC), YOLO e Whisper já rodam na GPU. O pico de VRAM no ensaio foi 4,7 de 12 GiB.
  - O que fica na RAM é o recorte que segue a pessoa quadro a quadro (numpy) e a legenda karaokê queimada pelo libass, que só roda na CPU.
  - Levar isso para a GPU é reescrever o render. Não compensa antes da estreia.
- **Ganhos menores que ficaram de fora:**
  - `-rc-lookahead 8` em vez de 32 tira mais ~300 MiB por render, mas mexe no controle de taxa do NVENC.
  - Os 99,5% do ensaio também somaram dois motores carregados ao mesmo tempo (o vivo na 8765 e o de ensaio na 8766).

### Posição e tamanho da legenda (Claude, 16/11, 23h55)

Pedido do usuário: legenda menor; com a tela dividida (streamer + jogo), exatamente na divisão; sem divisão, embaixo.

**O que estava errado.** Nos 8 cortes de `saida/pendentes` de 16/11, a legenda em PT ficava no centro da tela (y = 960). No corte dividido da JennaEmbers, ela caía por cima do rosto da streamer, e a divisão estava em y ≈ 1132. Isso acontecia porque a Cola pede a tradução com `burn: True`. A legenda traduzida é queimada por `multilingual/burn.py` numa base re-renderizada sem legenda, e esse caminho não sabia do layout. O layout gamer só calculava `caption_y` quando reservava faixa, com a posição `middle`.

**Decisão (`4fabbc0`).**
- **Plano em pilha** (`split`, `half`, `basecam`, `game_ui`, `mosaic`, `duo_split`): sempre devolve `caption_y` na linha entre a primeira e a segunda fileira. A legenda fica centrada nela com `\an5\pos`, qualquer que seja a posição do estilo.
- **Sem divisão** (`blurred`, `fullscreen` e as de webcam pequena `small_cam`/`circle_cam`/`dual_cam`): vale a posição do estilo. A config local agora usa `bottom`, ou seja, alinhamento 2 com 440 px de margem, acima da interface do TikTok/Shorts.
- **`render_opts.gaming.caption_y`** guarda a posição. `clean_base` devolve o `caption_y` da própria base re-renderizada, e `burn()` centra a legenda traduzida nele. O split de reserva do `video/cropper.py` também centra na divisão (y = 672, ou 1248 com a webcam embaixo).
- **Tamanho:** `config/settings.yaml` local (não versionado) passou de `font_size: 82, position: middle` para `62, bottom`, cerca de 24% menor. Com `bottom`, o layout não reserva faixa, e a legenda fica por cima da linha, sem encolher a webcam.

**Teste.**
- Novos: `test_split_captions_sit_on_the_dividing_line_without_a_band` (cam em cima e embaixo; `blurred` dá `None`) e `test_translated_captions_go_on_the_split_line` (o ASS queimado traz `\an5\pos(540,728)`).
- Suítes de legenda, layout gamer, cropper, saída final, tradução e seleção: **325 aprovados**.
- Render real de 2 s de um clipe da Twitch com Bebas Neue karaokê verde:
  - dividido: legenda em y = 728, na linha entre a webcam e o jogo;
  - `blurred`: legenda embaixo do jogo.
- Comparação conferida na imagem.

**Limitações.**
- O `settings.yaml` só é lido quando o motor sobe. Tamanho, posição e código novos valem depois do próximo reinício do motor, que fica com o operador.
- Cortes já renderizados guardam o estilo antigo (82, `middle`) em `render_opts.caption_style`. Se forem re-traduzidos, mantêm o tamanho antigo, mas já vão para a divisão.
- Webcam pequena sobre o jogo (PIP) não conta como tela dividida: a legenda fica embaixo.

### Ajustador da legenda na Mesa (Claude, 17/11, 00h50)

O usuário pediu um ajustador da fonte que passe a valer assim que ele salva, como a marca d'água CG.

**Decisão (`b3dc2b4` + `3dbe209`).**
- **Painel.** "Legenda dos próximos cortes" fica na Mesa, logo abaixo da autonomia. Ele reaproveita o `CaptionStyleControls` que a fila e o editor já usam: fonte, cor, tamanho, posição sem divisão, palavras por legenda, maiúsculas, destaque e cor do destaque. Os controles de karaokê ("palavras já ditas ficam acesas") e de "pop" ("a palavra falada cresce") entraram no mesmo componente. Os botões são Salvar e Desfazer.
- **Prévia.** É o próprio motor queimando com libass, em `GET /settings/caption-style/preview?style=<json>`, em cerca de 0,24 s, e o painel a mostra como `<img>`. A imagem traz dois quadros: a legenda na linha de uma tela dividida e numa tela sem divisão.
  - O exemplo antigo em CSS some nesse painel, porque o app não carrega o Bebas Neue e mostraria outra fonte.
  - A primeira versão usava POST com `blob:`, que a CSP do app (`img-src 'self' data: http://127.0.0.1:8765`) bloqueava. Por isso a rota virou GET.
- **Salvar.** `PUT /settings/caption-style` valida o estilo com `clean_style` (só chaves conhecidas, fonte da lista, cor `#RRGGBB`, posição válida, tamanho entre 40 e 200, palavras entre 1 e 6). O estilo vai para o `app_state` e troca `config["clips"]["caption_style"]`, a config viva que o worker copia com `deepcopy` no começo de cada tarefa. O próximo corte já sai com ele, sem reiniciar.
- **Subida do motor.** O estilo salvo no `app_state` vale sobre o `settings.yaml`.

**Teste.**
- `tests/test_caption_style_settings.py` (7): salvar vale na config viva e depois de recriar o app; estilo inválido devolve 400 e nada muda; a prévia é um PNG.
- `test_api_contract.py` verde, `gen_api_reference.py --check` em dia, `tsc` da web sem erro.
- **No Electron real** (`npm run dev`, porta 5173, motor recarregado às 00h43):
  - a prévia carregou com 720×640;
  - o tamanho 58 mudou a prévia;
  - "Salvar legenda" mostrou "Salvo. Os próximos cortes já saem com esta legenda.", e `GET /settings/caption-style` respondeu 58 na hora;
  - o tamanho voltou para 62 pelo próprio painel.

**Limitações.**
- Vale para os cortes novos. Os cortes que já estão na Mesa guardam o estilo da época em `render_opts.caption_style`.
- O executável do Tauri também foi recompilado (`cache/tauri-target/release/clipador-tauri.exe`, 17/11 00h42).
  - A cópia antiga ficou como `clipador-tauri.anterior.exe`, porque a janela aberta pelo Codex (pid 19304, de outra conta, acesso negado) ainda a usa.
  - Apagar a cópia antiga depois que essa janela fechar.

## Render e rastreamento na GPU (Antigravity, Codex e Claude, 17/11, 07h36)

Estes são os cartões 4 e 5 da rodada de desempenho com a VRAM livre. Os cartões 1 a 3 (Whisper e OCR) estão na [spec 05](05-ia-e-transcricao.md).

### Filtros do render em CUDA (Antigravity, Gemini 4 Hydrogen, `dc9f9cb`; Claude `c8447bf`)

`video/gpu_filters.py` testa o CUDA uma vez por processo: roda um grafo sintético de 0,1 s com `hwupload_cuda`, `scale_cuda`, `pad_cuda`, `overlay_cuda` e `hwdownload` e guarda o resultado.

Com CUDA disponível:
- `gaming/compose.gpu_filter_graph()` cobre os 11 presets.
- `video/cropper` também passa para a GPU: `_render_fit_blur`, `_render_split` e o ramo `top_safe` de `_render_tracked`.

**Como cada etapa roda:**
- **Decodificação:** NVDEC.
- **Escala, recorte e composição:** `scale_cuda`, `pad_cuda` e `overlay_cuda`, com coordenadas inteiras calculadas em Python. As expressões `(W-w)/2` saíam deslocadas no `overlay_cuda` do FFmpeg 8.0.1.
- **Fundo desfocado:** o quadro reduzido a 1/8 (136x240) recebe `gblur` na CPU e é ampliado na GPU.
- **Máscara do `circle_cam` e do `dual_cam`:** passou a ser estática, em vez do `geq` calculado a cada quadro.
- **Legenda:** libass na CPU depois de `hwdownload`. O caminho com `overlay_cuda` da legenda foi medido e descartado: SSIM 0,917, o dobro de VRAM e uma barra verde de 8 px.
- **Threads:** o FFmpeg roda com 1 thread de filtro, o que economiza ~130 MiB por processo.

**Regras que continuam valendo:**
- A legenda fica na linha da tela dividida, com `\an5\pos`.
- O `-shortest -shortest_buf_duration 1` foi mantido.

**Fallback:** se a sonda falhar, ou se o render na GPU falhar num clipe, roda o grafo de CPU de antes. Claude corrigiu a sonda para matar o ffmpeg que estoura o prazo de 15 s.

**Qualidade, CPU contra GPU, em um clipe de 6 s por caso.** Os 3 quadros lado a lado de cada caso estão em `D:\clipador-gta6\cache\ensaio-vram\antigravity\frames\`:

| Caso | SSIM | PSNR |
|---|---|---|
| `blurred` | 0,995 | 41,4 dB |
| `fullscreen` | 0,994 | 46,2 dB |
| `split` | 0,989 | 33,0 dB |
| `half` | 0,987 | 31,2 dB |
| `basecam` | 0,988 | 31,2 dB |
| `game_ui` | 0,967 | 27,9 dB |
| `mosaic` | 0,989 | 33,2 dB |
| `duo_split` | 0,986 | 31,9 dB |
| `small_cam` | 0,993 | 37,4 dB |
| `circle_cam` | 0,994 | 46,4 dB |
| `dual_cam` | 0,994 | 46,3 dB |
| `cropper_fit_blur` | 0,995 | 40,8 dB |
| `cropper_split` (em cima) | 0,981 | 30,5 dB |
| `cropper_split` (embaixo) | 0,983 | 31,1 dB |
| `cropper_top_safe` | 0,945 | 25,6 dB |

O Claude conferiu a olho os casos `cropper_top_safe`, `game_ui` e `half`: são iguais dos dois lados, com a legenda no mesmo lugar (na divisão no `half`, embaixo no `top_safe`).

### YOLO em lote (Codex, `903e8fc`; protótipo aplicado pelo Claude, `67e6aaf`)

**Perfil de tempo antes do lote (Codex):** no c0, o YOLO era 65% do rastreamento (6,9 de 10,6 s). No gamer, era 9%.

**Como funciona:** os quadros amostrados vão em lotes de 8, em FP32, numa só aquisição do lock, e na mesma ordem. O detector de cortes tem captura própria (`cut_cap`), por isso ler adiante não o afeta. Na CPU continua quadro a quadro. Um lote que falha tenta quadro a quadro e depois a CPU.

**Tempo do YOLO por clipe:**

| Clipe | Antes | Em lote |
|---|---|---|
| c0 | 6,9 s | 2,8 s |
| c1 | 9,9 s | 2,2 s |
| c2 | 9,6 s | 2,1 s |
| Twitch | 7,3 s | 1,5 s |

**Diferença no resultado:** as detecções brutas mudam pelo arredondamento do lote (caixa até 1,8 px, cabeça intermediária até 20 px). O corte final muda no máximo 0,09 px. O layout gamer ficou o mesmo: `half`, mesma webcam, `caption_y` 1140.

**Decisões:**
- O Codex recusou o lote pelo critério de igualdade estrita. O usuário aprovou aplicar, porque o corte final é o mesmo.
- O FP16 ficou de fora: não ganha nada.
- A correção `903e8fc`, também do Codex, faz o rastreamento respeitar a CPU quando o aquecimento CUDA falha. Ela também conserta o teste `test_second_speaker_render`, que quebrou com o prefixo `{\q2}` da legenda.

**Evidência:** `D:\clipador-gta6\cache\ensaio-vram\codex\RELATORIO-YOLO.md`.

### Medição combinada (Claude, código atual, fora do motor 8765)

Script `vram.py`, uma etapa por processo, com o tempo de iniciar o processo incluído.

| Etapa | Antes | Depois | VRAM antes → depois |
|---|---|---|---|
| 1 render (c0, `blurred`) | 33,9 s | **15,3 s** | +393 → +620 MiB |
| 3 renders em paralelo | 46 s | **32,3 s** | +1.177 → +1.861 MiB |
| Corte gamer (Twitch, `half`) | 72,9 s | **~23 s** (22,6 e 23,0) | +582 → +1.006 MiB |

A primeira medição do gamer, logo depois dos 3 renders, deu 64,3 s com tudo frio. Repetida, deu 23 s.

**RAM:** o Antigravity mediu a RAM do sistema com 3 renders: 89,4% antes, 81,9% depois. Com 4 renders foram 89,8%. A recomendação é manter `parallel_renders: 3`. Cada ffmpeg ainda segura ~1 GiB por causa do NVDEC, do NVENC com lookahead e do libass.

**VRAM no pior caso:** Whisper residente (2,1 GiB), mais YOLO e PANNs (0,25 GiB), mais 3 renders (1,9 GiB), mais a área de trabalho (~2 GiB): cerca de 6–7 GiB dos 12.

**Testes:**
- 305 testes de render, legenda e gamer verdes (`test_gpu_filters`, `test_gaming*`, `test_final_writes`, `test_caption_style_settings`, `test_cropper_zoom`, `test_subtitles_filter`, `test_render_length`, `test_second_speaker_render`).
- ~925 testes de tracker e gamer verdes com o lote.

**Vale depois de recarregar o motor.**

## Cor do segundo falante (Claude, 17/11, 09h23)

A legenda pinta de outra cor a fala de quem não é o streamer principal (`analysis/voice_turns.py`, opção `second_speaker` do estilo). Estava parada por dois motivos: os modelos não estavam em `clips-kitty/models/` e a opção estava desligada.

**O que foi feito:**
- `scripts/fetch_voice_model.py` baixou `wespeaker_resnet34_lm.onnx` (26,5 MB) e `pyannote_segmentation_3.onnx` (6,0 MB), com o SHA-256 conferido. A pasta `models/` fica fora do git.
- A opção foi ligada pela API do motor (`PUT /settings/caption-style`, o mesmo caminho do cartão "Legenda dos próximos cortes" da Mesa): `second_speaker: true`, cor `#5CE1FF`. Vale no próximo corte, sem reiniciar. Desligar é na própria Mesa.
- Os vídeos da Cola entram em `data/downloads`, que é a condição para o motor escutar as vozes (`voice_turns.in_library`).

**Medido no onnxruntime-directml 1.24.4 (CPU, como o código pede), num bloco real de 5 min (live de NBA 2K):**
- Perfil do vídeo: 6 vozes em 7,9 s, uma vez por vídeo.
- Por clipe de 50 s: 0,9 a 2,9 s. Outra voz em 4 das 6 janelas.
- Render do trecho de 100–150 s: as falas de outro jogador (3,7–25 s) saíram com as palavras ainda não ditas em azul-claro, e as do streamer em branco. A palavra falada continua verde nos dois casos. Quadros em `D:\clipador-gta6\cache\ensaio-vram\claude\voz\`.

**Testes:** 147 verdes (`test_game_text`, `test_voice_turns`, `test_second_speaker_render`, `test_caption_speakers`, `test_speaker_detection`, `test_packaging`, `test_whisper_gpu_libraries`).

**Limitação:** com o karaokê ligado, a diferença aparece só nas palavras que ainda não foram ditas.
