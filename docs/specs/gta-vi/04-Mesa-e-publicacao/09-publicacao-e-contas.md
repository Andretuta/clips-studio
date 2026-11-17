# Contas e publicação no YouTube e TikTok

Estado `implementado-com-dubles`: Electron, OAuth e autonomia preparados; ensaio real de conta/upload pendente do operador. Prioridade P0 para ensaio e P1 para evolução.

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

## Entrega Electron do Codex — 16/11/2026

Código preparado para ensaio após o **operador** recarregar motor/Cola. Nesta sessão não houve internet, consentimento real, upload nem reinício de serviços. Resultados finais dos testes e commits constam no registro ao fim desta nota.

### Caminhos existentes e escolha

| Caminho | OAuth e armazenamento | Ensaio |
| --- | --- | --- |
| YouTube direto | Cliente Desktop próprio; navegador do sistema aberto pelo IPC Electron; retorno loopback com state/PKCE pela biblioteca Google. Cliente e tokens por canal no cofre DPAPI do Windows. | Mesa → Aprovar e enviar ensaio → YouTube privado: força `privacy=private`, sem agendamento nem notificação de inscritos. |
| YouTube Composio | Chave local criptografada; OAuth guardado pelo provedor; ID da conta guardado no motor. | Painel Composio do editor, `privacyStatus=private`. |
| TikTok Composio | App TikTok e Auth Config próprio; navegador do sistema; tokens ficam no Composio e IDs da conta/envio no motor. | Mesa ou painel Composio: `publish=false`, caixa de entrada/rascunho, finalização pelo operador no TikTok. |
| Upload-Post e WoopSocial | Conectores existentes; exigem chave, conta e plano do fornecedor. | Não alterados nem escolhidos para a nova autonomia. |

O caminho TikTok implementado é **Composio**, sem novo cliente TikTok direto. `video.upload` entrega à caixa de entrada, não significa Direct Post público. Apps sem auditoria não devem ser tratados como autorizados a postar publicamente: Direct Post tem restrições de visibilidade/auditoria; rascunho também depende da capacidade liberada ao app e das contas de teste. Este código sempre usa rascunho no TikTok. Confira as permissões do app no painel; não houve consulta externa nesta rodada.

### YouTube: cadastro fora do código

1. Na [Google Cloud Console](https://console.cloud.google.com/), crie/escolha o projeto. Em APIs e serviços → Biblioteca, habilite **YouTube Data API v3**.
2. Em Google Auth Platform, preencha nome, suporte e público. Para o ensaio em **Testing**, inclua sua conta em **Test users**. A autorização em Testing pode expirar em sete dias. Produção/verificação são etapas posteriores conforme as exigências do Google; produção não substitui auditoria da API.
3. Escopos padrão: `https://www.googleapis.com/auth/youtube.upload` e `https://www.googleapis.com/auth/youtube.readonly`. Deixe playlists desligadas no ensaio: elas pedem adicionalmente `https://www.googleapis.com/auth/youtube`.
4. Crie OAuth Client de tipo **Desktop app**, não Web application. Copie client ID e client secret do mesmo cliente.
5. O retorno é **`http://127.0.0.1:<porta-efêmera>/`**, escolhido pela biblioteca. Não é a porta 8765, não requer retorno público nem cadastro de porta fixa no cliente Desktop. Navegador e motor precisam estar no mesmo PC. Consentimento expira em 300 s sem retorno.
6. No Electron, Configurações → **Publicar no YouTube** → habilitar → cole ID/secret nos campos → **Salvar credenciais OAuth** → **Conectar seu canal**. Escolha o canal no navegador e confira seu nome/canal padrão ao voltar.
7. Credenciais ficam atualmente em `D:/clipador-gta6/data/credentials`, criptografadas por DPAPI e ligadas à conta Windows do motor. Não colar em `.env`, `settings.yaml`, notas ou git. Não é necessário alterar arquivo versionado. Execute motor e app como a conta Windows do operador.
8. Se houver aviso de app não verificado ou limitação a privado, mantenha o ensaio privado e siga as instruções do painel Google. O cadastro e a liberação da conta não são comprovados pelos testes com dublês.

### TikTok/Composio: cadastro fora do código

1. Em [TikTok for Developers](https://developers.tiktok.com/), configure seu app (site, termos, privacidade e contas de teste/sandbox). Solicite **Content Posting API / Upload** e escopo **`video.upload`**, além da identidade exigida pelo conector, como `user.info.basic`. O rascunho deste fluxo não exige `video.publish`.
2. No projeto Composio, crie **Auth Config do toolkit TikTok** com o client key/secret desse app. Copie **integralmente a Redirect URI exibida nesse Auth Config** para o cadastro de redirecionamento do TikTok. O retorno é hospedado pelo Composio, não `127.0.0.1:8765`. A URI específica depende do Auth Config: não foi inventada nesta sessão offline.
3. No Electron, Configurações → **Canais de postagem → Composio**, cole API key do projeto no campo secreto e identificador **`ac_…`** no campo **Auth Config do TikTok**. Salve. Client key/secret TikTok são cadastrados no provedor e não no repositório.
4. Clique **Conectar TikTok**: abre `https://app.composio.dev/link/…` ou `https://connect.composio.dev/link/…` no navegador do sistema. Autorize a conta pretendida. Ao voltar, a janela atualiza ao ganhar foco; há também **Atualizar status**. Conectada significa `ACTIVE` no toolkit correto.
5. Envie mídia autorizada como rascunho e confira notificação/caixa de entrada no aplicativo TikTok. `publish_id` confirma aceitação, não publicação pública. Limites e aprovações do app/provedor ainda podem impedir o ensaio.

[Guia Composio TikTok](https://docs.composio.dev/kb/guide/toolkits-tiktok) · [Upload TikTok](https://developers.tiktok.com/doc/content-posting-api-reference-upload-video): referências para o operador, sem verificação online nesta entrega.

### R13: recibos, prazo e reconciliação

- SQLite `publish_receipts` guarda plataforma, ID remoto, estado e nota por tarefa. YouTube Composio fica aceito/concluído; TikTok fica **`awaiting_operator`** com `publish_id`. Resposta perdida após submissão vira **`uncertain`**. Reinício mantém a recuperação existente em **`interrupted`**, sem reenvio automático.
- Composio roda hash, staging, transferência e execução da ferramenta em processo filho com **prazo total de parede de 300 s**. O pai encerra o filho e libera o worker no prazo; após submissão, o resultado é incerto. Falha apenas no staging não declara postagem aceita. Teste do prazo usa dublê de processo e relógio curto, não upload real. O YouTube direto mantém o protocolo retomável existente; não recebeu prazo global novo de parede nesta entrega.
- Novo envio Composio para o corte/plataforma é bloqueado se já existe envio aceito, ativo, incerto ou interrompido. A reconciliação é **manual no painel/caixa da plataforma**, pois esta versão não presume uma ferramenta remota de status. Em Mesa → Autonomia e últimos envios, descreva a conferência e use **Conferi: chegou / não chegou**. API com sessão: `POST /composio/jobs/{id}/reconcile`, `outcome: found|absent`, nota de ao menos dez caracteres. Com ID remoto aceito, não é permitido declarar ausência para reenviar.
- A Mesa reserva nome/destino no banco: dois cliques devolvem o mesmo job. Queda entre reserva e vínculo final exige inspeção do histórico/banco; não há liberação automática. Reconciliação não dispara novo envio nem apaga histórico. O fluxo é conservador para evitar duplicatas.

### Autonomia opcional

Mesa → **Autonomia da IA e postagem automática**: edição e autoaprovação começam **desligadas**, salvas no banco. Padrão: limiar **0,90**, teto **2 reservas/hora**, YouTube direto **privado**. Público exige escolha explícita. TikTok continua rascunho. Não altera o settings local nem os canais da Cola.

A Cola entrega o par MP4/JSON e conserva `momento_chave` e transcrição temporizada disponível antes de liberar a fonte. Com a opção ligada, chama `/publication/mesa/{nome}/auto` com a sessão lida de `D:/clipador-gta6/data/plugins/session.secret`. O motor confere o sidecar persistido: sem score numérico finito em 0…1, ou abaixo do limiar, não autoaprova nem posta. A nota antiga 0…100 não vira confiança automaticamente. Score/limiar/motivos são registrados no sidecar e banco. Mudança de política permite reavaliar cortes que ficaram apenas em revisão.

A IA configurada em `llm.backend` revisa texto e pode remover até 2 s de cada borda, mantendo ao menos 5 s (ou toda a duração quando o corte já era menor). Transcrição temporizada limita o aparo aos intervalos fora das falas detectadas, com margem de 0,1 s (isso não comprova silêncio do áudio do jogo); sem evidência, bordas intactas. Mantém tag do jogo, áudio, legendas e enquadramento; não amplia trecho nem escolhe zoom. Exige a autorização de automação do plano no banco. Editar não autoriza postar.

A aprovação aplica a marca quando solicitada, conserva original e copia a versão aprovada para `data/clips/mesa`, com entrada própria na biblioteca. Publicação e tradução não dependem da fonte que a Cola libera depois. Há custo extra de disco para aprovado/original/biblioteca; nada é apagado em lote nesta entrega.

Rotas novas, com sessão: `GET/PUT /publication/autonomy`, `GET /publication/history`, `GET /publication/mesa/{nome}/details`, `POST /publication/mesa/{nome}/private-test` e `/auto`. O botão **Aprovar e enviar ensaio** envia explicitamente; **Aprovar** continua apenas aprovando. O histórico distingue envio aceito de resultado incerto e mostra IDs; a Mesa mostra score e motivos ou bloqueio por ausência do campo.

### Roteiro no Electron para 17/11

1. Como operador, recarregue motor e Cola pelos lançadores para carregar os commits. Abra **`D:\clipador-gta6\cola\abrir-app.cmd`**, sem `--web`: motor externo, sessão existente e caches no D:. O agente não reiniciou processos vivos.
2. Abra a Mesa, revise áudio, legenda, marca CG e texto. A prévia abre no mudo: ligue áudio para revisar. Deixe autonomia desligada.
3. Conecte YouTube pelos passos acima e confirme canal padrão. Na Mesa, escolha um corte autorizado, **YouTube privado → Aprovar e enviar ensaio**. Veja **Autonomia… → Últimos envios**, confira ID e visibilidade **Privado** no YouTube Studio. Para TikTok, ensaie outro corte como rascunho e confira sua caixa/notificação.
4. Resultado incerto: confira a plataforma e registre reconciliação antes de repetir. A ausência de resposta não comprova ausência do vídeo.
5. Escolha pessoalmente um canal autorizado e preencha `[gravador].canais` no `cola/config.toml` (a lista estava vazia e não foi preenchida pelo Codex). Recarregue a Cola pelo lançador. No Controle, confira canal, idade de segmento/bloco e chegada do corte à Mesa; confira analisador de chat e motivos/pontuação **Momento-chave**. Cortes antigos sem campo permanecem bloqueados para autopost.
6. Depois do ensaio, autorize automação do plano em Configurações → IA e ligue só a revisão editorial para um corte novo. Confira o resultado. Para testar autopost, escolha limiar 0,90, teto **1/h** e **Privado**. Confirme motivo, um único job e bloqueio do segundo corte na hora.

### Limitações

Sem login/upload real validado. Tauri continua sem abertura nativa OAuth nesta entrega. Captura/chat/transcrição e a emissão de `momento_chave` no resultado do corte pertencem aos cartões Antigravity: seus arquivos não foram editados por este agente. Sem esse contrato, a nova automação permanece bloqueada para postagem. R01/R02 e revisão de todos os IPCs continuam adiados. A suíte ampla de milhares de testes não foi repetida: os seis grupos históricos permanecem separados dos testes dirigidos desta entrega.

### Registro de testes — 16/11/2026, até 21h34 de Brasília

| Verificação | Resultado |
| --- | --- |
| `pytest -p no:cacheprovider -q -o addopts= tests/test_electron_publication.py tests/test_composio_publish.py tests/test_api_contract.py::test_the_reference_is_up_to_date` | **23 aprovados**, 12 avisos de depreciação FastAPI, 58,21 s. Inclui OAuth/account DPAPI com dublês, logs sem callback, YouTube privado, rascunho TikTok, recibo após reabrir banco, falta de score, teto/hora, duplicata, reconciliação e prazo com processo dublê. Relatório local `D:/clipador-gta6/tmp/electron-publicacao-final.xml`. |
| Render real no mesmo conjunto | Vídeo sintético de 10 s aparado para aproximadamente 8 s; faixa de áudio e original preservados. |
| Rodada ampliada: publicação, Mesa, contrato e painel (`291` casos naquele início) | **288 passaram, 1 ignorado, 2 falharam**: prazo do teste consumido pelo startup de spawn no Windows e referência API desatualizada pelas novas rotas. Corrigidos o harness (processo dublê) e o documento gerado; ambos passaram na rodada final de 23 acima. Não foi feita nova execução integral desses 291 após as correções. A coleta atual tem 292, pela inclusão do render real. |
| Cola, `python -m pytest -p no:cacheprovider -q` | **100 aprovados**, 430,30 s, no checkout compartilhado com as mudanças Antigravity presentes. Rechecagem final de `test_entrega.py`: **25 aprovados**, 125,70 s. |
| `npm test`, em `ui/` | **7 arquivos de teste aprovados, zero falhas**, 28,735 s: contas, OAuth real no Electron com HTTP/abertura do navegador dublês, cliente de publicação/URLs, recuperação, aprovação/texto, canal/chat e detector. |
| `npm run typecheck`; `npm run build` | Ambos com saída **0**. Build de main, preload e renderer concluído. |

Os testes UI inicialmente expuseram perfil/cache compartilhado no C: e corrida na mensagem transitória Ringing do harness antigo. Perfis temporários foram isolados no D:, idioma fixado, execução sequencial e relógio do teste controlado; a rodada final ficou verde. Nenhum pacote foi instalado. A referência API foi regenerada sem iniciar serviço. Não foram apagados `saida/`, `gravacoes/`, `testes-legenda/` nem saídas do operador.

Commits da entrega (16/11/2026, 21h36 de Brasília): `clips-kitty 7a1380e` (transporte/recibos), `0dc1a7a` (OAuth, API da Mesa e revisão editorial), `9427328` (Electron, testes UI e R03); `cola e1183d3` (entrega/autonomia). Sem push. Nenhuma alteração nos arquivos de captura, análise, transcrição, core/pipeline.py ou server/api.py dos agentes Antigravity.

### Revisão do Claude (16/11, 21h40)

- **Defeito corrigido (Cola `55b756c`):** a automação da Mesa roda dentro do tique da entrega. A Cola executa entrega, gravador e garimpeiro em fila. Com a revisão pela IA ligada e o acervo de 107 cortes pendentes, cada tique podia fazer até 20 chamadas de até 240 s. Isso seguraria o gravador (envio de blocos, guarda de disco, início e fim de live) por muito tempo.
- **Correção:** a automação para depois de 45 s por tique, cada chamada tem prazo de 120 s, e o que sobrar fica para o tique seguinte.
- **Testes:**
  - `test_automation_stops_at_the_tick_time_budget` falha sem o prazo e passa com ele;
  - suíte da Cola: **103 aprovados**.
- **Conferido sem mudança:**
  - automação desligada por padrão, e sem `momento_chave.score` não há postagem automática;
  - reserva em `desk_publications` antes de enviar, para não postar duas vezes;
  - teto por hora;
  - `safeHttps` só abre `https` sem usuário, senha ou porta;
  - a sessão vem de `D:\clipador-gta6\data\plugins\session.secret`, e o arquivo existe (45 bytes).
- **Limite da "autonomia aumentada":** a IA só corta até 2 s em cada borda, com base na transcrição, e reescreve título, descrição e hashtags. Ela não escolhe enquadramento, zoom, legenda nem uma janela de corte diferente. A escolha do momento continua com o Luna no motor. Ampliar isso fica para depois de medir os cortes reais.
- **Integração pendente:** o `momento_chave` só chega à Mesa quando o motor o expuser no clipe de `/jobs/{id}`. A entrega da Cola já copia o campo (`_copy`). Falta o cartão "[Motor]".
