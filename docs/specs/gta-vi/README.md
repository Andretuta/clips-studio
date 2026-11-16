# Specs do Clipador para a estreia do GTA VI

Este cofre reúne o estado operacional e as specs modulares do Clipador. Use este índice para encontrar o fluxo; cada pasta também tem um guia do que contém.

## Mapa por assunto

| Pasta | O que você encontra |
| --- | --- |
| [00 · Visão geral](00-Visao-Geral/README.md) | Índice principal, estado atual, riscos e próximos passos |
| [01 · Arquitetura](01-Arquitetura/README.md) | Janela desktop, Tauri/Electron, motor local e API |
| [02 · Captura e fila](02-Captura-e-fila/README.md) | Descoberta de lives, gravação, entrega de blocos, fila e armazenamento |
| [03 · Produção de clipes](03-Producao-de-clips/README.md) | IA, transcrição, seleção, edição, legendas, marca d’água e renderização |
| [04 · Mesa e publicação](04-Mesa-e-publicacao/README.md) | Revisão, controle operacional da Mesa, compilados e contas de postagem |
| [05 · Operação](05-Operacao/README.md) | Logs, diagnóstico, métricas, resposta a falhas e prontidão |
| [06 · Integrações](06-Integracoes/README.md) | Integrações opcionais, extensões, plugins e render remoto |
| [90 · Auditorias](90-Auditorias/README.md) | Revisão técnica, achados, severidade e evidências |

## Plugins do cofre

O cofre tem ferramentas para desenhar arquitetura e acompanhar tarefas. As tarefas ficam no [quadro da estreia](00-Visao-Geral/Quadro-da-Estreia.md) e o fluxo desenhado em [Fluxo do Clipador](Excalidraw/Fluxo%20do%20Clipador.excalidraw.md). Veja [quais plugins estão ativos e como usá-los](00-Visao-Geral/Plugins-do-Cofre.md).

## Por onde começar

1. Leia o [estado operacional](00-Visao-Geral/ESTADO-OPERACIONAL.md) para saber o que já existe e o que falta.
2. Consulte a spec da etapa que pretende alterar. As pastas seguem o fluxo da gravação até a publicação.
3. Antes de ampliar canais ou automações, confira [operação e diagnóstico](05-Operacao/10-observabilidade-e-operacao.md) e a [revisão de código](90-Auditorias/rev-code-review.md).

## Arquitetura local

| Camada | Runtime | Responsabilidade |
| --- | --- | --- |
| Janela desktop | Electron na operação atual. Tauri 2 em Rust com WebView2 no protótipo. | Exibe a mesma interface React e encaminha ações ao motor. |
| Interface de desenvolvimento | React e Vite na porta `5173`. | Mesa, Fila, Editor, Controle e Publicação. |
| Motor | Python 3.11, FastAPI e Uvicorn em `127.0.0.1:8765`. | API, fila, seleção de cortes, renderização, publicação e diagnóstico. A fila e o estado persistem em SQLite. |
| Computação local | FFmpeg para mídia, NVENC na GPU quando disponível e Whisper via CTranslate2 para transcrição. | Decodificação, análise, legendas e exportação. Luna usa a sessão do plano ChatGPT para seleção e metadados. |
| Cola | Serviço Python separado. | Detecta lives, grava segmentos com FFmpeg, monta blocos e os entrega ao motor pela API. |

O supervisor padrão inicia o motor com `python main.py serve --port 8765`. A janela Tauri se conecta ao motor já em execução. O arquivo de estado desta instalação é `D:\clipador-gta6\data\state.db`.

## Estado da migração em 16/11/2026

| Bloco | Estado | Entrega e verificação |
| --- | --- | --- |
| Janela Tauri | Protótipo local validado | React montou, a API retornou 105 cortes e o WebView2 decodificou uma prévia de 1080 px de largura no mudo. O motor e o servidor da interface são serviços locais externos à janela. |
| Análise visual | Implementada e testada | A leitura em lotes preservou os sinais. Em duas execuções por versão com vídeo sintético de 20 minutos, o pico mediano de RAM do processo Python passou de 333 para 38 MiB e o tempo mediano de 3,48 para 1,61 s. A instância do motor iniciada antes da alteração incorpora o código após reiniciar. |
| Funções nativas do Tauri | Próximo bloco de interface | Importar e exportar, recuperar a sessão local após reinício e abrir OAuth no navegador. Validar o fluxo completo antes da troca do lançador. |
| Desempenho do motor | Próximo bloco de processamento | Medir tempo, RAM e VRAM de transcrição e renderização com um bloco real de cinco minutos. Avaliar Rust por rotina a partir do perfil e da equivalência da saída. |

O resultado de RAM acima é da análise visual. A comparação entre as janelas será feita com a mesma tela, mídia e estado da fila. Consulte as [instruções do protótipo Tauri](../../../ui/src-tauri/README.md).

## Ordem de trabalho

| Ordem | Módulo | Objetivo |
| --- | --- | --- |
| 1 | [Desktop, API local e credenciais](01-Arquitetura/01-desktop-e-api.md) | Proteger a operação local, as chaves e a abertura no Windows |
| 2 | [Descoberta de lives e chat](02-Captura-e-fila/02-descoberta-de-lives.md) | Oferecer fontes de GTA VI e escolher o que gravar |
| 3 | [Gravação, blocos e entrega](02-Captura-e-fila/03-gravacao-e-entrega.md) | Sustentar captura e recuperação de blocos |
| 4 | [Fila e armazenamento](02-Captura-e-fila/04-fila-e-armazenamento.md) | Reservar capacidade antes do processamento e reagir à saturação |
| 5 | [Transcrição, Luna e seleção](03-Producao-de-clips/05-ia-e-transcricao.md) | Retomar etapas por causa do erro, preservando origem e texto |
| 6 | [Editor, legendas e marca](03-Producao-de-clips/06-editor-e-render.md) | Entregar o corte que o editor aprovou na prévia |
| 7 | [Mesa e Controle](04-Mesa-e-publicacao/07-mesa-e-controle.md) | Operar revisão e monitoramento com volume |
| 8 | [Compilados para YouTube](04-Mesa-e-publicacao/08-compilados-youtube.md) | Exportar vídeo longo com controle de recursos |
| 9 | [Contas e publicação](04-Mesa-e-publicacao/09-publicacao-e-contas.md) | Confirmar destino e resultado no YouTube e TikTok |
| 10 | [Observabilidade e operação](05-Operacao/10-observabilidade-e-operacao.md) | Correlacionar falhas e medir as condições de estreia |
| 11 | [Integrações e extensões](06-Integracoes/11-integracoes-e-extensoes.md) | Manter contratos e confiança isolados do fluxo principal |

Para a estreia, começar com 01 a 04 e 10. Validar 07 e 09 no primeiro ensaio ponta a ponta. Depois ampliar seleção, edição, compilação e integrações a partir dos limites medidos.

## Vocabulário

- **Cola** é o programa que acompanha lives, monta blocos e entrega cortes prontos à Mesa.
- **Motor** é o serviço Python que atende a API local e executa os trabalhadores de processamento e publicação.
- **Janela** é o aplicativo desktop que exibe o React. Electron e Tauri podem consultar a mesma instância do motor.
- **Segmento** é uma parte contínua da gravação. **Bloco** reúne segmentos com sobreposição antes de entrar no motor.
- **Tarefa** é a unidade persistida de trabalho. **Corte** é uma faixa de um vídeo, com metadados e arte renderizada.
- **Mesa** é a lista e a revisão de cortes. **Controle** reúne estado de gravação e operação.
- **Compilado** é um vídeo horizontal montado com cortes ordenados.
- **Envio aceito** significa que o provedor confirmou a entrega. **Publicado** significa que a plataforma confirmou o estado final correspondente.
