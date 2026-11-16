# Leitura do chat ao vivo: ferramentas avaliadas

Pesquisa do Claude em 16/11/2026, às 21h10 de Brasília. Ainda não há código usando estas opções. O cartão "[Gravação]" do quadro implementa a captura da Twitch na Cola (Python, sem dependência nova). O cartão "[Motor]" implementa a pontuação.

## Decisão

- **Captura fica na Cola, em Python.** O chat precisa estar junto do bloco gravado, e quem grava é a Cola. Assim a captura não depende da janela Electron ou Tauri estar aberta.
- **No Electron, só a exibição.** A Mesa pode mostrar o chat do bloco e a curva de pontuação que o motor calculou. A janela não faz uma segunda leitura do chat.

## Twitch

| Opção | Precisa de login | Situação em 2026 | Uso aqui |
| --- | --- | --- | --- |
| IRC por TLS (`irc.chat.twitch.tv:6697`), usuário anônimo `justinfan<n>` | Não | Segue funcionando. O `ws://` sem TLS foi desligado em 15/08/2025, mas o TLS continua. A Twitch atualizou as tags do PRIVMSG em 17/07/2026. Não há data de desligamento anunciada. | **Escolhida.** Usa só a biblioteca padrão do Python, uma conexão por canal. |
| EventSub `channel.chat.message` (WebSocket) | Sim: token de usuário com `user:read:chat` | É o caminho que a Twitch recomenda para novos recursos. | Plano B se o IRC for desligado. Exige OAuth da Twitch na Cola. |
| `@twurple/chat` (Node, TypeScript) | Opcional | Mantida; versão 7.3.0. | Só se a leitura passar para o Electron. |
| `tmi.js` | Opcional | Pouco mantida; a comunidade migrou para forks. | Não usar. |

## Emotes de terceiros (7TV, BTTV, FFZ)

O chat de GTA RP reage mais com emotes de terceiros (KEKW, OMEGALUL e outros) do que com os da Twitch. A tag `emotes` do IRC só marca os emotes da Twitch. Contar emotes de terceiros exige baixar a lista de cada canal:

- **BTTV:** `api.betterttv.net/3/cached/users/twitch/{id}`, que devolve os emotes do canal.
- **7TV:** API v3. O endpoint antigo foi desligado; conferir a documentação atual antes de usar.
- **FFZ:** API própria; conferir a documentação.

Bibliotecas que juntam os três, só para referência: `emotes-api`, `@mkody/twitch-emoticons` e `tmi-emote-parse`. Para o detector basta o nome do emote como palavra, sem imagem.

**Ganho barato:** carregar a lista de nomes uma vez por canal, ao iniciar a gravação, e contar tokens que batem com ela.

## Kick

- **Webhook oficial `chat.message.sent`.** Exige app registrado e servidor público para receber. Há relatos de atraso de horas e de mensagens fora de ordem em chats cheios. Não serve para a máquina local.
- **WebSocket Pusher, não oficial.** Não precisa de login: busca o `chatroom.id` em `kick.com/api/v2/channels/{slug}` e assina `chatrooms.{id}.v2`. Pode quebrar sem aviso.
- **Uso aqui:** fica para depois da Twitch. O Pusher é o caminho viável na máquina local.

## Detecção de momento

Projetos abertos olhados:

- `josec07/clipper`: rajada estatística mais palavras-chave, sem ML.
- `hougesen/twitch-highlight-finder`: frequência de mensagens e de emotes.
- `joaohenggeler/twitch-chat-highlights`: palavras e emotes em janela de 20 s.
- Pesquisa acadêmica: MINT (`dscig/twitch-highlight-detection`) e LIGHTOR.

Todos usam a mesma ideia do `analysis/chat_moments.py`: janela deslizante contra uma base móvel. O ganho real está em:

- calibrar com clipes populares reais (o cartão "[Motor]" mede recall e precisão);
- contar emotes de terceiros;
- pesar usuários únicos, para resistir a spam e copypasta.

Um modelo de ML só se justifica se a medida mostrar que as regras não bastam.

## Fontes

- [Changelog da Twitch](https://dev.twitch.tv/docs/change-log/)
- [Guia de migração do IRC para EventSub](https://dev.twitch.tv/docs/chat/irc-migration/)
- [Desligamento do WebSocket sem TLS](https://discuss.dev.twitch.com/t/decommission-of-non-secure-websocket-connections-to-twitch-irc-servers/64142)
- [@twurple/chat](https://npmjs.com/package/@twurple/chat)
- [Discussão sobre webhooks da Kick](https://github.qingwei-s.workers.dev/KickEngineering/KickDevDocs/discussions/147)
- [kick-api: cliente Pusher](https://docs.rs/kick-api/0.1.7/src/kick_api/live_chat.rs.html)
- [Wiki do Chatterino: serviços de terceiros](https://wiki.chatterino.com/Third_party_services/)
- [emotes-api](https://www.github.com/CrippledByte/emotes-api)
- [clipper](https://github.com/josec07/clipper)
- [twitch-highlight-finder](https://awesome.ecosyste.ms/projects/github.com%2Fhougesen%2Ftwitch-highlight-finder)
- [Artigo do LIGHTOR](https://www2.cs.sfu.ca/~jnwang/papers/lightor.pdf)
