# Editor, legendas, marca e renderização

Estado `ready-for-agent`. Prioridade P1.

## Problema

O corte precisa manter legibilidade no celular e identidade do canal. Fonte longa, layout variado e mudança de proporção podem alterar a posição das legendas, a marca e a duração percebida.

## Solução

Usar os mesmos contratos de posição, tempo e estilo na prévia e no vídeo final. Manter áudio sincronizado e separar edição de render caro.

## Histórias de usuário

1. Como editor, quero a prévia no mudo ao abrir um corte para controlar o som do ambiente.
2. Como editor, quero legendas discretas e centralizadas com até duas linhas para manter o gameplay visível.
3. Como editor, quero editar e dividir palavras longas e hifenizadas de modo legível para evitar três linhas.
4. Como editor, quero ligar ou desligar a marca CG com @CortesGameroffc por corte para escolher a identidade da postagem.
5. Como editor, quero ajustar tamanho e opacidade e ver a marca percorrer a área real da imagem para evitar que fique restrita às margens.
6. Como editor, quero conferir o resultado na proporção de publicação sem perder o enquadramento após exportar.
7. Como operador, quero recuperar um vídeo se o render falhar para publicar uma versão revisada em seguida.

## Decisões de implementação

- A janela exibe a prévia e envia o pedido de exportação pela API. O motor Python coordena a renderização com FFmpeg e seleciona NVENC quando o meio de codificação e o hardware permitem.
- Obter zonas de legenda e marca a partir das dimensões reais e do layout. Posicionar legenda central dentro da zona que preserva a imagem e limitar a duas linhas tanto na divisão quanto no arquivo renderizado.
- Manter o PNG CG e o texto do perfil como grupo visual. A trajetória pode cruzar zonas internas da área de gameplay, com margens proporcionais e tamanho/opacidade resolvidos de modo consistente.
- Separar o crédito ao streamer da marca do canal. Guardar estilo e indicação de marca já incorporada para reaproveitamento em compilados.
- Reusar a trilha de edição, guardar o original e concluir o MP4 temporário antes de substituir uma mídia. Isolar falta de GPU, falta de espaço e falha de codec.
- Compartilhar as regras com a Mesa e compilação. Relatar progresso e permitir cancelar render pelo motor.

## Decisões de teste

- Costura principal: exportação pelo editor com fontes controladas. Conferir a duração, proporção, trilhas e quadros renderizados em vários tempos.
- Testar duas linhas em fontes longas, ritmo rápido e hifens, e visibilidade da marca em posições internas com tamanho e opacidade distintos.
- Reaproveitar testes de legendas, layout e re-render. Comparar a prévia no mudo com o MP4 final que conserva sua faixa de áudio.
- Verificar a prévia, a escolha de pasta e a exportação no Tauri. Medir tempo, RAM e VRAM do render por perfil, com a mesma mídia, opções e saída esperada em cada execução.

## Fora do escopo

Detecção automática de cada elemento da interface de GTA VI e garantia de impedir edição ou reutilização de uma cópia.

## Notas

Inclui saída vertical para Shorts/TikTok e preservação de aspect ratio para material horizontal.

## Autonomia editorial opt-in — 16/11/2026, Codex

No código atual, `analysis/highlights.py` e seus prompts já selecionam janelas, início/fim, hook, título e hashtags a partir da transcrição e sinais. Fusão/regras ajustam candidatos; Whisper e o construtor de legendas cuidam das palavras/tempos. Enquadramento depende de layout, detecção e render, sem novo comando livre do Luna para zoom. Na Mesa, texto, destinos, marca e aprovação eram manuais; duração/layout eram revistos no editor quando a fonte ainda existia.

`llm/editorial.py` adiciona revisão **desligada por padrão** da cópia pronta: título até 100 caracteres, descrição até 3.000, até 12 hashtags e aparo de no máximo 2 s por borda. Valida formato/números, recusa NaN e mantém tag do jogo. Transcrição temporizada limita aparo ao silêncio com 0,1 s de margem; sem evidência, não muda bordas. Mantém ao menos 5 s, ou todo corte que já era menor. Não oferece ferramentas nem URLs ao modelo.

`video_editor/desk.py` usa FFmpeg com prazo para o aparo, mantém áudio e conserva original. Aparar vídeo já legendado conserva a sincronia das legendas incorporadas. Marca é aplicada na aprovação se ainda não estava incorporada. Blur sem webcam e polish desligado não mudaram. É respeitada a autorização de automação do plano no banco; falha da IA ou decisão inválida impede seguir para postagem.

Testes de limites, fala, ausência de transcrição e tag em `test_electron_publication.py`; entrega/transcrição em `cola/tests/test_entrega.py`. Números finais e roteiro na [spec 09](../04-Mesa-e-publicacao/09-publicacao-e-contas.md). Não houve avaliação artística com Luna nem medição de render em gameplay real. A revisão é posterior ao pipeline e não exigiu alterar `core/pipeline.py`; emissão de `momento_chave` continua com o agente do motor.
