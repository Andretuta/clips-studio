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
