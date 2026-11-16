# Plugins do cofre

O modo restrito foi desativado neste cofre para permitir plugins da comunidade. Os dois plugins abaixo estão instalados e ativos.

| Plugin | Versão | Para que serve no Clipador | Abrir |
| --- | ---: | --- | --- |
| Excalidraw | 2.29.2 | Desenhar arquitetura local, caminhos de gravação e publicação, limites entre janela, motor e Cola. Os desenhos ficam guardados no cofre e podem ser ligados às specs. | Abra a paleta com `Ctrl+P` e procure por `Excalidraw`. |
| Kanban | 2.0.51 | Acompanhar tarefas do roteiro em colunas arrastáveis. Os quadros são arquivos Markdown do cofre. | Abra a paleta com `Ctrl+P` e procure por `Kanban: Create new board`. |

## Em uso

- **Quadro Kanban:** [Quadro-da-Estreia.md](Quadro-da-Estreia.md). Colunas `Depende do usuário`, `A fazer · P0 (antes da estreia)`, `A fazer · P1`, `Fazendo` e `Feito`. Uma tarefa por cartão, com tag de prioridade (`#P0`), ID do achado (`#R04`) e link para a spec. A evidência detalhada fica na spec.
- **Excalidraw:** [Fluxo do Clipador](../Excalidraw/Fluxo%20do%20Clipador.excalidraw.md), na pasta `Excalidraw/` configurada no plugin (arquivos `.excalidraw.md`). Mostra o caminho da live até a publicação e marca em vermelho os riscos abertos. Atualizar junto com a spec quando a arquitetura mudar.
- **Claude Code:** `D:/clipador-gta6/.claude/` faz o Claude ler este cofre no início de cada sessão (resumo do estado e do quadro) e cobrar a atualização do estado, da spec e do quadro quando altera código. Regras em `.claude/rules/cofre-obsidian.md`.
- Ambos os plugins funcionam com os arquivos locais do cofre. Os recursos do Excalidraw que usam imagens por URL, OCR, scripts ou serviços de IA podem acessar serviços externos quando acionados.

## Integrações externas

A execução de plugins da comunidade está habilitada para este cofre. Nenhuma conta de armazenamento, GitHub, IA externa ou sincronização foi conectada aqui. Conexões com esses serviços dependem de escolher o provedor e autorizar a conta dentro do próprio serviço.

> **Manutenção do Kanban:** o catálogo oficial atualmente indica que o plugin está procurando novos mantenedores. Seus quadros permanecem em Markdown no cofre, mesmo que no futuro você troque de plugin.
