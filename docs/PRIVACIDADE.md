# Privacidade

O jogo foi feito para rodar com crianças e público de feira, então a regra é simples: **nada é gravado e nada sai do computador.**

## Nenhuma imagem é gravada

- **Nenhuma imagem, vídeo ou dado de rosto é gravado em disco.**
  - O código não tem nenhuma chamada de salvar imagem. Confira com `grep -rn "imwrite\|image.save" caretas/`.
  - O log vai só para o console e registra eventos do jogo e FPS, nunca imagens nem valores de emoção.
  - O `.gitignore` bloqueia `*.png`, `*.jpg` e vídeos, para nada disso ir parar no repositório por engano.

## Tudo fica na memória

- a câmera guarda só o quadro mais recente;
- as 3 "fotos" da vitória e do relatório são recortes pequenos em RAM, **zerados e descartados** quando o operador chama o próximo jogador (ou o relatório volta sozinho). Para desligar as fotos: `ui.victory_snapshots: false`;
- o relatório guarda só números (probabilidades, valência, excitação, tempos) em RAM, também zerados no reset. Nada disso vai para o log;
- o modo "Por dentro da IA" mostra o recorte 224×224 na tela, mas ele só existe na memória, quadro a quadro.

## Nada é enviado para lugar nenhum

- A internet só é usada no setup, para baixar pacotes e modelos públicos (com SHA-256 conferido).
- Durante a execução, o jogo **bloqueia qualquer conexão de rede** para fora da máquina (`caretas/offline.py`).
- Ele foi testado rodando **sem nenhuma interface de rede** (namespace de rede isolado no Linux), completando uma partida inteira a cerca de 57 FPS.

## Fotos do público

As pessoas podem fotografar a tela do projetor com o próprio celular. Isso é escolha delas: o sistema não guarda nada.
