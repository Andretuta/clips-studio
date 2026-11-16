# Gravação, blocos e entrega ao motor

Estado `ready-for-agent`. Prioridade P0.

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
- Manter as janelas atuais de segmentos com sobreposição até validar outra duração. Registrar o início e fim reais e marcar lacunas detectadas.
- Separar sondagem e supervisão do trabalho de concatenação e ingestão. Limitar concorrência desses trabalhos e usar rodada justa entre canais.
- Fixar prazo por tentativa de sondagem, concatenação e cópia. Usar publicação atômica do MP4 e estado durável por identidade do bloco.
- Remover origem só após confirmar e persistir a identificação da tarefa, ou verificar que o mesmo bloco já está concluído. Isolar respostas inconclusivas e corrupções.
- Definir limites separados, alertas e reserva de disco para segmentos, blocos, envio, logs e vídeo pronto. Deduplicar pelo canal e intervalo da gravação.
- Reconhecer processos antigos pelo PID, início e parâmetros esperados. Reiniciar captura travada com orçamento e registrar lacunas.

## Decisões de teste

- Costura principal: Cola, motor simulado e pequenos arquivos MPEG-TS. Simular fila cheia, timeout, confirmação perdida, processo bloqueado, disco baixo e duas origens concorrentes.
- Provar recuperação após interrupção antes e depois da confirmação. Medir se uma origem saudável continua produzindo durante a falha simulada.
- Reaproveitar os testes de concatenação, rejeitados, sobreposição, disco e entrega. Acrescentar cenário de segmento corrompido e retomada.
- Conferir que a gravação e o envio continuam durante a troca da janela desktop e que o Controle recupera o estado ao reabrir.

## Fora do escopo

Redundância distribuída de gravadores e download retrospectivo de lives sem gravação ou VOD.

## Notas

Conservar originais recuperáveis para diagnóstico e permitir descarte explícito. Relaciona-se aos achados R04, R06 e R08.
