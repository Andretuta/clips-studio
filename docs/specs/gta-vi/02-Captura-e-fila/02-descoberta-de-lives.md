# Descoberta de lives e sinais do chat

Estado `ready-for-agent`. Prioridade P0 para origem e P1 para chat.

## Problema

O operador precisa localizar canais de GTA VI na hora da estreia. Desde 16/11 a configuração usa só o garimpeiro: clipes da Twitch de GTA V e VI das últimas 2 h, com 50+ visualizações. O gravador não tem canais fixos. Erros no provedor, mudanças de categoria e reconexões podem ser confundidos com uma live fora do ar.

## Solução

Exibir lives candidatas no Controle, escolher as fontes a gravar e manter dados recentes mesmo durante uma indisponibilidade temporária. Usar sinais agregados do chat como opção de seleção de momentos.

## Histórias de usuário

1. Como operador, quero ver lives por categoria, idioma e plataforma para montar minha lista de captura.
2. Como operador, quero indicar canais autorizados e confirmar quais vão gravar para controlar o volume e a origem do material.
3. Como operador, quero distinguir ao vivo, fora do ar, consulta falhou e informação antiga para saber quando agir.
4. Como operador, quero que uma indisponibilidade temporária preserve a gravação em curso para evitar perder o jogo.
5. Como operador, quero atualizar uma categoria ausente e encontrar os canais depois do lançamento para evitar depender de reinício.
6. Como editor, quero ver picos de atividade do chat alinhados ao vídeo para encontrar momentos com reação.
7. Como mantenedor, quero respeitar a próxima janela de consulta do provedor para evitar novas recusas durante a estreia.
8. Como mantenedor, quero consumir notificações repetidas uma única vez para evitar iniciar duas gravações.

## Decisões de implementação

- Consultar a API oficial primeiro. Paginar resultados de descoberta e dividir listas de canais conforme os limites do provedor. Usar cache com validade e indicar a idade do dado.
- Aplicar espera por provedor e credencial em HTTP 429, com limite, variação e horário de retomada. Distinguir falha de credencial, 403, 5xx, offline confirmado e resposta antiga.
- Resolver categoria novamente se um nome estiver ausente ou o cache vencer. A lista de descoberta alimenta seleção explícita e limite simultâneo de gravações.
- Usar o mecanismo de eventos da Twitch quando habilitado. Identificar duplicatas, reconciliar após reconexão e usar consulta periódica dentro do orçamento como contingência.
- Agregar contagens e sinais do chat somente com a conexão e os escopos adequados. Medir atrasos em relação à gravação e manter processamento por vídeo quando o chat estiver indisponível.

## Decisões de teste

- Costura principal: ciclo completo de descoberta com provedor simulado, relógio controlado e 20+ canais elegíveis. Cobrir paginação, expiração, 401, 403, 429, 503 e resposta lenta.
- Verificar que uma falha em uma plataforma não bloqueia a outra nem muda uma gravação ativa para offline.
- Partir dos testes de Helix, gravador, eventos da Twitch e fluxos de transmissão. Testar mensagens duplicadas e sinais atrasados com o relógio da captura.

## Fora do escopo

Gravar todos os resultados, contornar recusas da plataforma e enviar mensagens ao chat.

## Notas

A categoria é um rótulo da plataforma. O operador confirma que a transmissão está mostrando o conteúdo desejado. Relaciona-se ao R07.

### Primeiro ciclo real do garimpeiro (16/11/2026)

- **18h56:** Cola reiniciada. Os dois primeiros tiques, às 18h56 e às 19h01, falharam com `WinError 10013` no `POST https://id.twitch.tv/oauth2/token`. O mesmo `python.exe` da `.venv`, rodado como `andre`, conectava normalmente.
- **Causa:** o laço da janela "Cola" (`cmd` aberto em 15/11 às 02h04) rodava como `CodexSandboxOffline`, com token restrito. É o usuário do sandbox do Codex, e esse usuário não tem saída para a internet. O laço foi aberto por uma sessão do Codex dentro do sandbox, e todo `python -m cola` que ele subia herdava o bloqueio. O motor roda como `andre` e não foi afetado.
- **Como conferir:** pegar o dono do processo `python -m cola` pelo token. O SID terminado em `-1003` é `CodexSandboxOffline`; em `-1001` é `andre`.
- **Correção:** laço encerrado e Cola aberta de novo como `andre`, sem restrição. Às **19h04:53** o garimpeiro enviou 2 clipes (tarefas 74 e 75).
- **Regra para os agentes:** a Cola e o motor sobem pelo usuário, ou fora do sandbox. Um processo de longa duração aberto pelo sandbox do Codex fica sem rede.

### Ensaio ponta a ponta (16/11/2026, 19h04–19h10)

| Etapa | Clipe AngelKnivez, "bonk" (en, 25 s) | Clipe Chatterbox, "Don't Mind Me" (en, 28 s) |
| --- | --- | --- |
| Tarefa no motor | 74: download, HEVC → H.264, Whisper `large-v3-turbo` na GPU, render NVENC. 2,0 min | 75: o mesmo caminho. 1,1 min |
| Transcrição | 1 trecho, só até 4,4 s | 7 trechos, até 27,4 s |
| Tradução PT (Cola → motor) | 76: ~1 min | 77: ~1 min |
| Entrega | `saida/pendentes/twitch_AngelKnivez_20261116-190651_158.mp4` às 19h08 | `twitch_Chatterbox_20261116-190800_159.mp4` às 19h09 |
| MP4 | 1080×1920, 60 fps, H.264 + AAC; áudio com média de −17,5 dB e pico de −1,1 dB | 1080×1920, H.264 + AAC; média de −20,8 dB e pico de −1,1 dB |
| Legenda | Karaokê verde em PT só nos primeiros 4 s | Karaokê verde em PT no clipe inteiro |
| Mesa | `GET /mesa/cortes`: 107 cortes, os dois novos listados | idem |

O que o ensaio mostrou:

- **Crédito do streamer:** sai certo (`@AngelKnivez`, `@Chatterbox`, no canto superior esquerdo), pelo perfil `Crédito @streamer` que a Cola cria.
- **Marca Cortes Gamer:** não entra no render da Cola. O `submit_url` não manda `cortes_gamer_watermark`. Na Mesa, a caixa da marca começa desmarcada nesses cortes (`rascunhoDe` em `Mesa.tsx` só a liga se o JSON trouxer `cortes_gamer_watermark` ou `cortes_gamer_baked`). Aprovar sem ligar a caixa manda o corte sem a marca.
- **Decisão do usuário (16/11, 19h20):** marca ligada por padrão. Desde a Cola `dca570b`, `_copy` grava `cortes_gamer_watermark: true` no JSON de todo corte entregue, traduzido ou não. A caixa já vem marcada na Mesa, e a marca entra ao aprovar; dá para desmarcar num corte. O teste `test_pt_clip_is_copied_with_sidecar` confere a chave, e a suíte da Cola passou com 70 testes. A Cola foi recarregada às 19h26. Os 107 cortes que já estavam na Mesa (inclusive o 158 e o 159) continuam sem a chave e precisam da caixa marcada à mão.
- **A marca funciona quando aplicada:** `video_editor.cortes_gamer.render` rodou sobre uma cópia do 159 fora da Mesa, em 13 s. Saiu o logo CG com `@CortesGameroffc` na faixa do jogo, e a duração e o áudio ficaram iguais. A Mesa não foi tocada.
- **Outro:** não entra porque `clips.outro: false` no `settings.yaml` local. Foi escolha de configuração, não falha.
- **Qualidade:** o Whisper perdeu a maior parte da fala do clipe 158 (corrigido em `35a226b`, detalhe na [spec 05](../03-Producao-de-clips/05-ia-e-transcricao.md)). As hashtags geradas não citam o jogo: #hambúrguer, #churrasco e #comerporansiedade no 159; #cinema e #contagemregressiva no 158.
- **Detalhe interno:** a pasta em `data/clips` leva o nome de quem criou o clipe na Twitch (`unspeakableglitched`, `SherrieBifana`), não o do streamer. A entrega usa o `broadcaster_name` da Cola, então o nome final sai certo.

### Tag do jogo (#GTA6/#GTAV) no título e nas hashtags (16/11/2026)

Commit: `cola` `5ab6354`.

- **Causa raiz:** o garimpeiro descartava o mapeamento `game_id → nome do jogo` após consultar a Twitch Helix e chamava `POST /jobs` sem `hashtags`; além disso, para clipes em inglês, o passo `POST /translate` reescrevia título e hashtags sem receber tags obrigatórias do jogo.
- **Correção:**
  - `cola/garimpeiro.py` + `cola/kitty.py`: `game_hashtag()` converte `"Grand Theft Auto VI"` → `#GTA6` e `"Grand Theft Auto V"` → `#GTAV` (com fallback alfanumérico); `run_once` passa `hashtags=[tag]` em `submit_url` e grava `"jogo"` em `meta`.
  - `cola/gravador.py`: armazena `_canal_jogo` a partir da consulta ao vivo da Twitch e grava `"jogo"` no `meta` dos blocos.
  - `cola/entrega.py` (`_with_game_tag` em `_copy`): garante `#GTA6`/`#GTAV` no `titulo` (respeitando o limite de 100 caracteres) e em `hashtags` (sem duplicar caso já exista em outra capitalização), inclusive após tradução EN→PT, além de salvar `"jogo"` no sidecar `.json`.
- **Testes:** `test_gta6_clip_passes_gta6_hashtag_and_game_meta`, `test_job_recorded_for_delivery`, `test_submit_url_includes_hashtags_when_given`, `test_delivered_sidecar_includes_game_tag_in_title_and_hashtags` e `test_game_tag_is_not_duplicated_and_fits_title_limit` dentro da suíte da Cola (**79 aprovados**). A Cola em execução precisa ser recarregada para valer em produção.

