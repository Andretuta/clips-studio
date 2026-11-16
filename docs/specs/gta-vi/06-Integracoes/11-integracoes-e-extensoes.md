# Integrações, plugins e render remoto

Estado `ready-for-agent`. Prioridade P2.

## Problema

O projeto inclui Connected Accounts, OBS, plugins e render remoto. Cada integração amplia a confiança exigida. Mudanças nesses pontos podem afetar a captura local ou criar dependência de serviços durante a estreia.

## Solução

Definir contratos e limites para as integrações que o operador escolher. Separar a operação de estreia dos experimentos com fontes e extensões.

## Histórias de usuário

1. Como mantenedor, quero identificar quais integrações estão ligadas para reproduzir o ambiente de operação.
2. Como operador, quero aprovar os dados e permissões de um plugin para escolher o nível de acesso que aceito.
3. Como operador, quero revogar a credencial de uma integração específica para manter as outras disponíveis.
4. Como operador, quero parear um renderizador explícito e ver o estado de transferência para decidir se delego um render.
5. Como mantenedor, quero receber eventos de OBS e Twitch com identidade, ordenação e deduplicação para evitar tarefas repetidas.
6. Como operador, quero que o motor local continue selecionando e renderizando cortes quando uma integração opcional cair.
7. Como mantenedor, quero avaliar um conector de leitura para fonte sem API oficial em ambiente isolado para medir sua estabilidade antes de adotá-lo.

## Decisões de implementação

- Manter a API oficial e os clientes do Clipador como caminho principal de integração. Tratar API Anything como hipótese de leitura para fonte sem suporte oficial, com revisão da operação e sem enviar credenciais ao catálogo.
- Preservar manifesto, permissões efetivas de interfaces e aprovação de versão. Considerar plugin um código executado com permissões da conta até existir isolamento verificável.
- Usar credenciais específicas e revogáveis para OBS, Connected Accounts e workers. Autorizar reenfileiramento e envio de arquivos por escopo.
- Manter descoberta remota opcional, autenticar cada trabalhador e limitar bytes, tempo e frequência por credencial. Retomar transferência com validação de integridade.
- Definir a indisponibilidade de cada integração como degradada para o fluxo núcleo e documentar a reversão.

## Decisões de teste

- Costura principal: contrato da integração em ambiente de teste com credenciais fictícias. Exercitar conexão, revogação, falha transitória e retomada.
- Reaproveitar testes de Connected Accounts, plugins, eventos e render remoto. Verificar que o caminho local segue com as extensões desativadas.
- Em avaliação de adaptador web, medir resultados de leitura e tratamento de alterações de contrato com respostas sintéticas antes de acessar provedores reais.

## Fora do escopo

Instalar plugin ou dependência de scraping durante a estreia e abrir acesso externo ao motor. A migração da janela tem sua própria [spec de desktop](../01-Arquitetura/01-desktop-e-api.md).

## Notas

A revisão examinou a fronteira declarada das extensões. Um ensaio separado é necessário antes de ativar qualquer integração opcional em rede.
