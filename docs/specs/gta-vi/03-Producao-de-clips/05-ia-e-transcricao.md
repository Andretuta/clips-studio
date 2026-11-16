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

