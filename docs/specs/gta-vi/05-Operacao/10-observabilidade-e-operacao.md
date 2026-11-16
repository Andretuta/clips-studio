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
