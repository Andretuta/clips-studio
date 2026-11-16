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
