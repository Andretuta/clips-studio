# Mesa de revisão e Controle

Estado `ready-for-agent`. Prioridade P0 para integridade e P1 para busca.

## Problema

A Mesa organiza arquivos e metadados em pastas. Com vários canais, cresce a quantidade de cortes pendentes e a chance de aprovar durante uma cópia, perder uma edição ou carregar a lista inteira a cada atualização.

## Solução

Mostrar lotes e estado dos canais no Controle. Tornar a entrega e as decisões recuperáveis e manter a Mesa rápida com histórico grande.

## Histórias de usuário

1. Como operador, quero ver canal, categoria, idade do último segmento e do último bloco para distinguir off-line de captura parada.
2. Como editor, quero filtrar a Mesa por canal, estado, hora e nota para encontrar rapidamente os melhores cortes da live.
3. Como editor, quero copiar título, descrição e hashtags em português para publicar sem refazer o trabalho.
4. Como editor, quero manter o foco e a posição da prévia durante atualizações da lista para revisar vários cortes.
5. Como editor, quero que o corte só apareça quando o MP4 e os metadados estiverem prontos para evitar aprovar um arquivo incompleto.
6. Como operador, quero aprovar ou descartar exatamente uma vez para evitar arquivos órfãos após dois cliques ou uma queda.
7. Como operador, quero um caminho para recuperar originais e edições para resolver falhas de disco ou vídeo em uso.
8. Como operador, quero abrir no Controle o erro correspondente ao corte para descobrir em que etapa ele parou.

## Decisões de implementação

- Usar os mesmos cortes e status do motor na Mesa e no Controle de Electron, Tauri e modo web. A janela Tauri já consultou a Mesa e decodificou um quadro no mudo em ensaio local.
- Usar estados pendente, aprovado e descartado com identidade estável. Publicar a entrada da Mesa só depois que mídia e metadados estiverem completos.
- Fazer aprovação e descarte idempotentes, conservando original quando houver transformação. Uma operação pendente deve ser reconciliável após reinício.
- Acrescentar paginação, contagem incremental e filtros à listagem. Agrupar consultas do editor e limitar a geração de capas por origem e concorrência.
- Atualizar o Controle com estado e idade do dado por canal, fila e plataforma. A prévia abre sem som e permanece utilizável com dados parciais de monitoramento.
- Proteger mídia, metadados e transições pela sessão adequada. Descrever erros com causa e ação possível em português.

## Decisões de teste

- Costura principal: rotas da Mesa e Controle sobre pastas temporárias. Exercer entrega, tentativa concorrente, falha de escrita, arquivo aberto e recuperação.
- Verificar paginação, ordenação e tempo de resposta com centenas de itens sintéticos sem depender dos dados atuais do operador.
- Reaproveitar testes de Mesa, entrega, sessão e prévias. Conferir via interface filtro, cópia do texto e ação sobre um item.

## Fora do escopo

Apagar cortes históricos em lote e publicar automaticamente ao aprovar.

## Notas

O Controle é a porta de entrada da operação de estreia. Relaciona-se aos achados R04, R10 e R11.

**Duração do bloco fixa na interface (16/11/2026, revisão do Claude).** `ui/src/renderer/src/lib/mesa.ts` define `BLOCO_S = 960` (blocos antigos de 16 min). A Cola passou a gerar blocos de 4 min + 1 min de sobreposição (300 s). Efeitos: no Controle, a largura de cada bloco na linha do tempo (`Controle.tsx`, eixo e `width`) fica 3,2× maior; na Mesa, a faixa "de onde veio na live" espreme os cortes no primeiro terço e o horário final mostra início + 16 min (`Mesa.tsx`, `somaHora`). Os 105 cortes antigos são de blocos de 16 min, então um valor fixo não serve aos dois. **Resolvido no mesmo dia.** O gravador põe `bloco_s` (bloco + sobreposição, em segundos) no job e a entrega copia o campo para o JSON do corte (Cola `60a3131`). A API da Mesa devolve `bloco_s` na posição da live e `dur_s` em cada bloco do Controle, com 960 para cortes antigos sem o campo (`353ae66`). A constante `BLOCO_S` saiu de `mesa.ts`. O Controle também cai em 960 quando fala com um motor anterior à mudança. Testes em `test_mesa_api.py`, `test_gravador.py` e `test_entrega.py`. O motor que está no ar precisa reiniciar para servir os campos novos.
