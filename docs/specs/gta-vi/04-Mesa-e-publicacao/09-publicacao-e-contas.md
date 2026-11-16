# Contas e publicação no YouTube e TikTok

Estado `ready-for-agent`. Prioridade P0 para ensaio e P1 para automação.

## Problema

O operador precisa publicar Shorts, vídeos longos e envios para a caixa do TikTok. Um envio lento ou de resposta incerta pode prender a fila ou ser repetido sem saber se a plataforma já o recebeu.

## Solução

Usar destinação explícita, estado persistido e reconciliação com o provedor. Exibir o que foi aceito, o que requer ação do operador e o que efetivamente foi publicado.

## Histórias de usuário

1. Como operador, quero escolher e validar o canal conectado para evitar postar na conta errada.
2. Como operador, quero distinguir Shorts, vídeo longo e caixa do TikTok para cumprir o fluxo de cada formato.
3. Como operador, quero ver a visibilidade desejada antes de enviar para controlar quando o público vê o vídeo.
4. Como operador, quero receber o ID remoto ao terminar para localizar o vídeo ou a entrega na plataforma.
5. Como operador, quero saber quando o resultado é incerto para conferir a plataforma antes de repetir.
6. Como operador, quero que uma falha de rede retome o envio quando o provedor permitir para reduzir o retrabalho.
7. Como operador, quero ver quando uma cota volta ou a credencial precisa ser reconectada para tomar a ação certa.
8. Como editor, quero poder exportar MP4 e copiar o texto quando integração estiver indisponível para publicar manualmente.
9. Como mantenedor, quero impedir duplicata após reinício ou clique repetido para operar durante pico com confiança.

## Decisões de implementação

- O motor gerencia as conexões e a fila de publicação. Na etapa de migração do Tauri, abrir autorizações OAuth no navegador do sistema e consultar no motor o novo estado da conta ao voltar à janela.
- Definir identidade de envio por revisão da mídia, plataforma, conta e intenção. Persistir o identificador remoto e, quando suportado, a sessão de envio sem expor seu endereço.
- Separar reservado, transferindo, aceito, aguardando ação, publicado, falhou e resultado incerto. Transições devem sobreviver ao reinício e preservar histórico.
- Distinguir timeout antes da criação, falha retomável e resposta perdida após aceitar. Verificar o provedor antes de reemitir, quando a API permitir. Pedir conferência quando não houver evidência suficiente.
- Respeitar 429, quota e sinais de reautenticação por conta e provedor. Limitar prazo total e bloquear repetição automática com resultado incerto.
- Manter YouTube Composio privado e TikTok no fluxo de caixa até o operador escolher uma forma explícita de publicar. Mostrar status e arte final mesmo no caminho de exportação manual.
- Usar cache curto na validação de conta, invalidado ao reconectar ou trocar o destino. Gate de estreia prevê ensaio privado, com conta indicada e mídia autorizada.

## Decisões de teste

- Costura principal: rotas e trabalhador de publicação contra transportes simulados. Verificar OAuth, conta trocada, quota, timeout durante e depois da transferência, reinício e cancelamento.
- Reaproveitar testes de Composio, classificação de erros e histórico de publicação. Exigir que o ID da entrega TikTok possa ser consultado após reiniciar.
- Rodar os testes do painel com o resolvedor do frontend e o catálogo de idioma. Conferir estados e consultas em português, além das expectativas do fluxo existente.
- No Tauri, verificar a abertura e o retorno do OAuth, incluindo autorização concluída, cancelada e expirada. Usar uma conta de ensaio antes de mudar o lançador de operação.
- Fazer ensaio real em separado com autorização e visibilidade escolhidas. Verificar o ID do YouTube, caixa do TikTok, vídeo longo e fallback manual.

## Fora do escopo

Postagens públicas no ensaio, acesso automático a canais adicionais e uso de sessão de navegador no lugar de OAuth.

## Notas

A aprovação do canal e o estado final devem vir do provedor. Relaciona-se aos achados R02, R13 e R17.
