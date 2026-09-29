# Guia do operador (dia do evento)

Tudo o que quem cuida do estande precisa: teclas, checklist e o que fazer durante a feira. Para ajustar a dificuldade no local, veja [CALIBRACAO.md](CALIBRACAO.md).

Nos comandos abaixo, use `start_windows.bat` no Windows ou `./start.sh` no Linux.

## Controles do teclado

| Tecla | Ação |
|---|---|
| **Enter**, **Espaço**, **→** ou **Page Down** | "Próximo": na vitória, pula para o relatório; no relatório, **chama o próximo jogador**; durante o jogo, reinicia a partida. Page Down/→ permitem usar um **passador de slides** como controle |
| **S** ou **↑** | Revisão humana: **SIM**, a IA acertou |
| **N** ou **↓** | Revisão humana: **NÃO**, a IA errou (dá para trocar a resposta) |
| **Mouse** | No relatório, os botões SIM, NÃO e PRÓXIMO JOGADOR também funcionam com clique |
| **R** | Reinicia a partida na hora |
| **E** | Modo explicação "Por dentro da IA" (liga/desliga; pausa o jogo) |
| **M** | Liga/desliga o som |
| **F** ou **F11** | Alterna tela cheia / janela |
| **D** ou **F1** | Liga/desliga o painel de debug (calibração) |
| **C** | Troca de câmera (no Windows, entre as câmeras de `usb_hardware_id`) |
| **Q** ou **Esc** (duas vezes) | Sai. O primeiro toque só mostra um aviso, para uma criança não fechar o jogo sem querer |

Resets automáticos:

- o jogador saiu do quadro por mais de 3 s (durante a partida; no relatório ele pode sair à vontade);
- o relatório ficou 90 s na tela sem ninguém apertar ENTER (`game.report_timeout`; 0 = só pelo botão);
- a câmera caiu durante a partida.

Depois da vitória (5 s) ou do "QUASE!" (4 s), o jogo vai sozinho para o relatório e **espera o botão**.

---

## Checklist

### Na véspera (com internet)

- [ ] Setup (`setup_windows.bat` ou `./setup.sh`): termina com os testes passando.
- [ ] `--check`: **TUDO PRONTO!**
- [ ] Partida completa com a webcam do evento e o projetor, em tela cheia, até o relatório (S/N e ENTER).
- [ ] Som saindo na caixa/TV certa e num volume bom (`audio.volume` no config; **M** muta).
- [ ] Calibração com 3 ou mais pessoas ([CALIBRACAO.md](CALIBRACAO.md)).
- [ ] **Teste offline de verdade**: desligue o Wi-Fi e tire o cabo, abra pelo atalho e jogue uma partida.
- [ ] No computador:
  - Energia: nunca suspender e nunca desligar a tela.
  - Modo **Não perturbe** ligado, para não aparecer notificação no projetor.
  - Pausar as atualizações automáticas por uma semana.
- [ ] Carregador na mochila. O notebook na tomada roda mais rápido.

### Chegando no local

- [ ] Ligue o **projetor e a webcam antes** de abrir o jogo.
- [ ] No Windows, aperte **Win + P** e escolha **Duplicar**, ou **Somente segunda tela**. Em "Estender", a tela cheia vai para o monitor principal.
- [ ] Posicione a câmera **na altura do rosto das crianças** (cerca de 1,2 m).
- [ ] **Luz de frente** para o jogador, nunca contra janela.
- [ ] Fundo com pouco movimento.
- [ ] Marque com fita, no chão, onde o jogador fica (cerca de 1 m da câmera).
- [ ] Abra o jogo pelo atalho e faça uma partida de teste.
- [ ] Aperte **D** e faça o teste do neutro rápido com a luz do local. Depois aperte **D** de novo para esconder o painel.
- [ ] Opcional: uma plaquinha "Pode tirar foto da tela! O computador não guarda nenhuma imagem."

### Durante

- Fim de partida → relatório. Pergunte ao jogador **"A IA acertou?"**, aperte **S** ou **N** e depois **ENTER** quando o próximo estiver pronto. Se a pessoa disser "eu estava fingindo!", ótimo gancho: *a IA lê a expressão do rosto, não o que a pessoa sente*, e por isso um humano sempre confere.
- Quer explicar como funciona → **E** (modo "Por dentro da IA"); **E** de novo volta ao jogo.
- Barulho demais ou som atrapalhando o estande vizinho → **M**.
- Algo estranho → **R** reinicia a partida.
- Criança travada numa careta → dê a dica em voz alta. O tempo acaba em 60 s e o jogo volta sozinho.
- Jogo fechou → ele reabre sozinho em 3 s. Se não reabrir, abra pelo atalho.
- Câmera sumiu → espere uns segundos (reconexão automática). Se não voltar, confira o cabo e veja [WEBCAM.md](WEBCAM.md).

### No fim

- **Q** duas vezes para sair.
