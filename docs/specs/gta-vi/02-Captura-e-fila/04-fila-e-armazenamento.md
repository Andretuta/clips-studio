# Fila, admissão e armazenamento

Estado `ready-for-agent`. Prioridade P0.

## Problema

O limite de cinco vagas conta processamento de fontes. Importações fazem sondagem e cópia antes de checar o limite, e alguns trabalhos de CPU/GPU não entram nessa capacidade. Admissão e deduplicação têm passos separados.

## Solução

Reservar um orçamento transacional antes do trabalho caro. Dar identidade aos pedidos e uma política de prioridade e espaço por tipo de tarefa.

## Histórias de usuário

1. Como operador, quero que a fila rejeite cedo quando estiver cheia para liberar disco e tempo de resposta.
2. Como operador, quero ver a capacidade real por tipo de tarefa para decidir se inicio um compilado.
3. Como operador, quero que pedidos repetidos retornem a tarefa existente para evitar processar a mesma live duas vezes.
4. Como editor, quero cancelar um trabalho e liberar sua vaga de forma consistente para continuar editando.
5. Como operador, quero reservar capacidade para novas lives sem deixar traduções e exportações esperando indefinidamente.
6. Como mantenedor, quero que uma reinicialização recupere reservas e uploads temporários para remover arquivos órfãos com segurança.
7. Como operador, quero uma pausa que sobreviva à reconexão para controlar o que o motor volta a processar.

## Decisões de implementação

- Manter FastAPI, Uvicorn e SQLite como origem do estado da fila. Electron, Tauri e modo web consultam o mesmo motor e recebem a mesma identificação de tarefa e capacidade.
- Escolher capacidade por recurso e tipo, incluindo processar, importar, traduzir, renderizar e compilar. Fixar quais atividades competem por disco, CPU e GPU.
- Unificar no motor admissão, deduplicação por identidade e criação da tarefa em transação. As entradas por URL, arquivo, observador, exportação e Cola devem respeitar o mesmo orçamento.
- Emitir resposta recuperável com a tarefa existente ou código de lotação. Usar identidade estável da fonte, opção do trabalho e intenção de refazer.
- Para mídia local, reservar vaga e bytes antes da cópia e fazer sondagem limitada. Publicar arquivo pronto por renomeação e liberar reserva ao falhar.
- Definir cotas e política justa para evitar inanição por prioridade. Medir idade da fila, tempo por etapa e ocupação de disco; reconciliar reservas após queda.

## Decisões de teste

- Costura principal: rotas do motor com SQLite temporário e importador controlado. Disparar pedidos simultâneos e comprovar que o limite e a deduplicação se mantêm.
- Exercitar fila cheia, pausa persistida, cancelamento, recuperação e liberação de reserva. Comparar uso de disco antes e depois de recusa.
- Criar uma tarefa de teste, alternar entre os clientes e conferir que eles leem o mesmo estado, inclusive após reiniciar a interface.
- Usar os testes do contrato da fila, recuperação e importação; ensaiar captação, render e compilação com pequenas mídias locais.

## Fora do escopo

Work stealing, processamento em cluster e adoção de nova tecnologia de banco.

## Notas

A latência da API deve ser medida em separado da duração do trabalho. Relaciona-se aos achados R05, R08 e R12.
