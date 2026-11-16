# Diagnóstico, incidentes e ensaio da estreia

Estado `ready-for-agent`. Prioridade P0.

## Problema

O motor, a Cola e os provedores registram falhas com identificadores distintos. A consulta de diagnóstico local ajuda com tarefas falhas, porém interrupções, requisições sem tarefa e histórico do motor após reinício ficam difíceis de correlacionar.

## Solução

Dar ao operador e à IA a mesma linha do tempo com dados filtrados, impacto e próximo passo. Fazer um ensaio com limites de recursos antes da cobertura.

## Histórias de usuário

1. Como operador, quero procurar um bloco e encontrar as etapas até o corte pronto e a postagem para identificar atrasos.
2. Como operador, quero ver há quanto tempo captura, fila e provedor não avançam para agir antes de perder cobertura.
3. Como mantenedor, quero ler falhas, interrupções e resultados incertos mesmo depois de reiniciar o motor para diagnosticar a causa.
4. Como operador, quero que a IA leia dados de diagnóstico com escopo próprio para ajudar a interpretar erros.
5. Como operador, quero saber se o log expirou, está ausente ou está indisponível para distinguir as causas de uma resposta vazia.
6. Como mantenedor, quero que chaves, links de sessão e outros dados sensíveis sejam removidos antes de salvar ou exibir eventos.
7. Como operador, quero ver estado da Twitch, Kick, plano ChatGPT, codificação e publicação antes da estreia para escolher o caminho de contingência.
8. Como operador, quero uma sequência para degradar de duas capturas para uma, reduzir compilação ou postar manualmente para manter a cobertura.

## Decisões de implementação

- Gerar um identificador na captura e propagá-lo até os trabalhos de análise, render, Mesa e publicação. Associar eventos a componente, fase, instante, código e tarefa.
- Manter registros persistidos com rotação e limite total. Filtrar em cada ponto de gravação e resposta. Fornecer logs consultáveis mesmo quando o motor principal estiver parado, por ferramenta local.
- Aproveitar as rotas de diagnóstico existentes com autenticação, paginação, limite de bytes, filtro por entidade e estado explícito de disponibilidade. Reduzir dependência de texto bruto.
- Limitar conexões e frequência de eventos. Repor estado após reconexão consultando o snapshot atual quando houver perda de eventos.
- Medir intervalos de sondagem, idade de fila, latência por fase, ocupação do disco e erros por provedor. Definir metas de ensaio e gatilhos com capacidade medida no PC.
- Distinguir falha de arranque da janela, falha ao carregar o React e indisponibilidade do motor. Medir CPU e RAM da janela em conjunto com seus subprocessos e registrar RAM, VRAM e duração por etapa do motor e dos seus processos de mídia.
- Codex pode consultar a API local. Para futura integração MCP, expor ferramentas específicas de leitura e manter escopo distinto de ações de publicação.

## Decisões de teste

- Costura principal: consultar a API após um fluxo sintético desde captura até entrega. Conferir correlação, causa, limite, rotação e recuperação.
- Reaproveitar os testes de diagnóstico, contrato e eventos. Usar segredos fictícios e mídia local. Verificar que credenciais não aparecem no registro persistido e que a consulta respeita credencial de leitura.
- Ensaiar com um e depois dois canais autorizados e plataformas simuladas em falha. Medir CPU, GPU, disco, latência da API, atraso da primeira entrega e tempo de recuperação.
- Registrar configuração, mídia, número de execuções e qual processo foi medido em cada comparação. Conferir a saúde do motor independentemente do resultado da janela Tauri.

## Fora do escopo

Enviar logs a serviços públicos, abrir porta na internet e alterar ou repetir tarefas automaticamente por uma ferramenta de diagnóstico.

## Notas

Se o motor não estiver atendendo, o diagnóstico usa o coletor local e os registros persistidos. Relaciona-se aos achados R01, R02, R10 e R14.

### Ensaio de falhas: motor parado, fila cheia e resposta perdida (16/11/2026)

Commits: `clips-kitty` `c6ede52` · `cola` `5ab6354`.

- **Defeitos encontrados na causa raiz:**
  1. `POST /videos/local` (`clips-kitty/server/api.py`) não consultava `queue.duplicate_of(d, vid)`, permitindo enfileirar o mesmo bloco duas vezes se a primeira resposta se perdesse.
  2. Tanto `POST /jobs` quanto `POST /videos/local` verificavam `queue.capacity(d) <= 0` antes de `queue.duplicate_of(d, vid)`: se a tentativa anterior tivesse ocupado a 5ª vaga (`MAX_ACTIVE = 5`), o reenvio após timeout recebia HTTP `409` em vez de `already_queued` com `queued_job_id`.
  3. Na Cola, HTTP `429` não disparava `QueueFull` (`cola/kitty.py`); e, quando o motor já havia concluído a tarefa entre o timeout e a retomada (`already_processed`), `garimpeiro.py` e `gravador.py` não recuperavam o `job_id` pelo `video_id`. Além disso, `gravador.py` apagava o bloco `.mp4` mesmo quando a resposta vinha sem `job_id` nem confirmação de duplicata.
- **Correções:**
  - `clips-kitty/server/api.py`: `duplicate_of` movido para antes da checagem de capacidade em `POST /jobs` e adicionado antes da capacidade em `POST /videos/local`.
  - `cola/cola/estado.py`, `kitty.py`, `garimpeiro.py`, `gravador.py`: tabela `tentativas` registra envios iniciados; `409` e `429` levantam `QueueFull`; `already_queued` usa `queued_job_id`; `already_processed` com tentativa ativa recupera o `job_id` via `GET /jobs` (`job_for_video`); `gravador.py` preserva o bloco em disco em qualquer erro ou resposta inesperada.
- **Comandos e resultados:**
  - Suíte da Cola (`D:/clipador-gta6/clips-kitty/.venv/Scripts/python.exe -m pytest -p no:cacheprovider -q` em `D:\clipador-gta6\cola`): **79 aprovados** em 161,25 s (inclui `test_outage_leaves_clip_unsent_and_retries_once`, `test_lost_response_recovers_already_queued_and_already_done_without_duplicating`, `test_block_lost_response_recovers_job_without_duplicating_or_losing_block` e `test_block_waits_on_429_and_is_kept_on_unexpected_reply`).
  - Suíte direcionada do motor (`.../python.exe -m pytest -p no:cacheprovider -q tests/test_api_contract.py tests/test_local_upload.py tests/test_transcript_repair.py tests/test_whisper_gpu_libraries.py tests/test_cancel.py` em `D:\clipador-gta6\clips-kitty`): **77 aprovados** (inclui `test_reposting_same_local_file_recovers_queued_job_even_when_queue_full`).
  - Ensaio isolado contra `clips-kitty` real (`uvicorn` + `create_app` na porta `127.0.0.1:8766`, dados em `D:\clipador-gta6\cache\ensaio-falhas`, encerrado e limpo ao final, sem tocar na `8765`):
    - **(a) Motor parado:** `garimpeiro.run_once` e `gravador._send_blocks` falharam com `ConnectionError` sem marcar enviado nem apagar o bloco; quando a porta `8766` subiu, criaram **1 tarefa** cada.
    - **(b) Fila cheia (409 real com 5 vagas ocupadas):** ambos mantiveram clipe e bloco pendentes; ao liberar a fila, criaram **1 tarefa** cada.
    - **(c) Resposta perdida (timeout pós-POST na 5ª vaga `queued` e também já `done`):** no retorno sem timeout, o motor respondeu `already_queued` (mesmo com fila cheia) ou `already_processed`; a Cola recuperou o mesmo `job_id`, não abriu tarefa duplicada e `entrega.tick` gerou **1 MP4 + 1 JSON** cada em `saida/pendentes`.
- **Observação operacional:** o motor vivo (`127.0.0.1:8765`) e a Cola ao vivo continuam com o código anterior até serem recarregados pelo operador.

