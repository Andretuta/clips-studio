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
