# Desktop, API local e credenciais

Estado `ready-for-agent`. Prioridade P0.

Protótipo Tauri validado com a API, a Mesa, uma prévia no mudo e a chave de sessão (`sessao: 200`). A próxima etapa é completar as funções nativas para operação diária.

## Problema

A janela do Clipador, a interface web e a Cola chamam o mesmo motor. A sessão protege algumas ações, enquanto outros caminhos usam apenas o endereço local. As permissões herdadas do disco também abrangem arquivos de configuração e código.

## Solução

Adicionar a janela Tauri por etapas usando o frontend React e o motor Python existentes. Restringir cada ação à conta ou ao cliente que precisa dela e recuperar a sessão após reinício. Manter Electron e modo web disponíveis durante o ensaio.

## Histórias de usuário

1. Como operador, quero que só minha sessão execute ações sobre projetos e canais para impedir mudanças por outro cliente local.
2. Como operador, quero que o supervisor consiga reabrir o motor e a janela recupere a sessão para manter o Controle acessível.
3. Como operador, quero abrir o modo web quando o Electron falhar para continuar usando Mesa, Fila e Publicação.
4. Como operador, quero saber quais portas estão em uso antes de abrir a interface para evitar conectar ao processo errado.
5. Como mantenedor, quero que o software valide a janela de origem de cada ação nativa para preservar a fronteira entre navegador e desktop.
6. Como operador, quero guardar chaves e históricos em locais com permissões adequadas para evitar acesso por outras contas do Windows.
7. Como mantenedor, quero instalar e validar o Tauri em ambiente de teste para promover a janela após passar pelo fluxo diário.
8. Como editor, quero escolher arquivos e pastas no Tauri para importar, revisar e exportar pelo mesmo motor.
9. Como operador, quero abrir OAuth no navegador e voltar à janela com o estado atualizado para conectar minhas contas.

## Decisões de implementação

- Tauri 2 em Rust abre o React no WebView2. O protótipo carrega a interface local na porta `5173` e consulta o motor Python na porta `8765`. A janela tem perfil próprio e o supervisor mantém o motor como processo independente.
- **Sessão local, feita em 16/11 (`672a7ce`).** O comando Rust `sessao_motor` lê `CLIPADOR_SESSAO` (o `session.secret`) a cada pedido e devolve a chave à interface. A capability `sessao-do-motor` libera só esse comando e só para `http://localhost:5173/*`, e o `build.rs` declara a lista de comandos. O perfil do WebView2 vai para `CLIPADOR_WEBVIEW_DIR`, no D. Limite: a janela confia no que escutar na `5173`. O frontend empacotado tira esse limite.
- Evoluir a ponte nativa aos poucos: seleção de arquivos e pastas, exportação e abertura de OAuth no navegador. Usar operações específicas da interface com permissões mínimas.
- Manter o motor em loopback. Exigir autenticação para API de escrita e leitura sensível. Dar credencial própria e escopo mínimo à Cola e às integrações.
- Definir origens exatas para a interface web, a janela instalada e a conexão de eventos. Validar o identificador da janela, o frame e a navegação permitida antes de cada IPC privilegiado.
- Limitar links externos a protocolos e destinos necessários. A página de doação deve permanecer isolada das funções nativas.
- Verificar permissões efetivas de código, sessão, configuração, mídia e estado para as contas que realmente operam o motor e a Cola. Persistir chaves no cofre do sistema e excluir o acesso de grupos amplos.
- Definir como a janela descobre uma sessão nova e recupera o estado visual. O modo web deve ter bootstrap autenticado e estado equivalente nos fluxos da estreia.
- Ensaiar instalador e atualização do Tauri depois de validar as ações nativas. Usar o fluxo atual na cobertura até a validação de ponta a ponta. Verificar a reversão para o lançador Electron e a alternativa web.

## Decisões de teste

- Costura principal: inicialização do processo e testes de contrato da API. Verificar autorização por perfil e recuperação após iniciar um motor novo, com identidades de teste.
- Para IPC, testar políticas de destino e autorização por unidade e conferir os fluxos de escolher arquivo, idioma e abrir OAuth na janela instalada.
- Verificar permissões em ambiente controlado do Windows sob as contas de serviço previstas. Cobrir leitura e alteração somente de arquivos sintéticos.
- Reaproveitar os testes de sessão, segurança de caminhos, contrato e modo web. Ensaiar a janela nativa e a alternativa web no Windows.
- Repetir a verificação do protótipo com a Mesa carregada e a prévia no mudo. Para promover a janela, completar um ensaio de importar, gerar, revisar, exportar e recuperar a sessão após reiniciar o motor.
- Comparar a memória das janelas com a mesma tela, mesma mídia e API no mesmo estado. Conferir o encerramento sem erro de ciclo de vida do WebView2.

## Fora do escopo

Exposição do motor na internet, reescrita integral do motor em Rust e instalação de complementos novos para a estreia.

## Notas

A solução deve manter prévias no mudo e interfaces em português do Brasil. A verificação via WebView2 saiu com código `0` e registrou o aviso `1412` ao fechar. A captura de tela automatizada expirou. Relaciona-se aos achados R01, R02 e R03.
