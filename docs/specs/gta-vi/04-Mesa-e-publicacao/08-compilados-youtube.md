# Compilados e vídeo longo do YouTube

Estado `ready-for-agent`. Prioridade P1.

## Problema

O operador quer montar um vídeo longo com cortes da Mesa e biblioteca. Preparar todas as partes pode consumir disco e manter o trabalhador ocupado enquanto chegam blocos ao vivo.

## Solução

Permitir ordenar cortes existentes, estimar tempo e tamanho, exportar um 16:9 verificável e encaminhá-lo a um destino explícito.

## Histórias de usuário

1. Como editor, quero selecionar cortes da Mesa e da biblioteca para montar um vídeo temático.
2. Como editor, quero reordenar e pré-visualizar a sequência para controlar a narrativa.
3. Como editor, quero ver a duração total estimada e o espaço necessário para decidir se exporto durante a cobertura.
4. Como editor, quero usar cortes verticais e horizontais juntos para manter o conteúdo visível no 16:9.
5. Como editor, quero que áudio e vídeo sigam sem lacunas entre partes para evitar cortes bruscos não planejados.
6. Como editor, quero aplicar a marca CG somente quando necessário para evitar duas marcas em um corte.
7. Como operador, quero que cancelar ou falhar libere a reserva e preserve a ordem editada para repetir a exportação.
8. Como operador, quero abrir a exportação como vídeo longo no YouTube para escolher conta, título e visibilidade.

## Decisões de implementação

- O cliente desktop envia a seleção e acompanha o progresso pela API. O trabalhador Python monta e verifica o MP4 de saída com FFmpeg.
- Identificar cada origem por corte e revisão. Validar pelo menos dois cortes diferentes, sua existência e duração no momento do processamento.
- Guardar a ordem do projeto e os estados de admissão, processamento e exportação. Limitar duração, espaço intermediário e concorrência no mesmo orçamento do render.
- Normalizar saída horizontal, base de tempo e trilha de áudio. Definir preenchimento seguro para mídia de outra proporção e tratamento para corte sem áudio.
- Manter o conhecimento sobre a marca já incorporada na origem. Usar um arquivo final verificado pelo motor antes de abrir a etapa de publicação.
- Retornar progresso por parte, erro localizado e resultado com duração, formato e referência acessível ao operador.

## Decisões de teste

- Costura principal: criar compilado na API, acompanhar tarefa e inspecionar o arquivo com FFprobe e amostras de quadros.
- Usar cortes de cores distintas, áudio com e sem som, proporções diferentes e um com marca incorporada. Conferir ordem, duração, dimensões, áudio e ausência de marca duplicada.
- Reaproveitar testes de compilação e re-render. Exercitar seleção que some, fila cheia, reserva de disco e cancelamento.

## Fora do escopo

Transições automáticas, edição musical e postagem pública no momento da exportação.

## Notas

O envio ao YouTube usa a etapa de publicação, com a mesma seleção de canal e verificação de estado. Relaciona-se ao achado R12.
