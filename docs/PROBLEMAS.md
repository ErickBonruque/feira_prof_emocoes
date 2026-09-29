# Problemas comuns

Rode primeiro o `--check` (`start_windows.bat --check` ou `./start.sh --check`): ele confere modelos, GPU, câmera e tela, e aponta o que falhou.

## A câmera não abre ("CÂMERA DESCONECTADA")

Veja [WEBCAM.md](WEBCAM.md): tem o passo a passo para Windows e Linux.

## O jogo está lento

- Aperte **D** e veja os FPS: a tela deve ficar em cerca de 60. O `--check` também mostra os ms de cada modelo.
- **A câmera entrega poucos FPS** → quase sempre é pouca luz: com pouca luz, a webcam alonga a exposição e perde FPS. Ilumine o rosto de frente. Mais opções em [WEBCAM.md › Imagem e desempenho](WEBCAM.md#imagem-e-desempenho-windows-e-linux).
- **O painel mostra CPU em vez de GPU** → confira se o `nvidia-smi` funciona (driver NVIDIA instalado). Na CPU o jogo funciona, mas usa mais processador.
- Baixe a câmera para `width: 640` e `height: 480`, e o `detector.input_width` para 480.
- O notebook deve estar **na tomada**, no modo de energia "Melhor desempenho", com os outros programas fechados.

## A detecção está errada

- **Não acha o rosto:**
  - luz fraca ou contra a luz;
  - boné, óculos escuros ou máscara;
  - pessoa muito longe → aproxime, ou diminua `detector.min_face_width`.
- **Travou na pessoa errada:**
  - aperte **R** com só o jogador na frente;
  - suba `center_weight` e `min_face_width`.
- **Troca de jogador sozinho:** isso só acontece se o jogador sumir por mais de 3 s (`detector.lost_seconds`).
- **Emoção errada ou difícil demais:** veja [CALIBRACAO.md](CALIBRACAO.md). A tristeza é a mais difícil de "atuar": ensine a careta.
- **"FIQUE SÉRIO(A)" repete:** a pessoa está rindo na calibração. Peça cara séria; depois de 3 tentativas, o jogo usa um neutro padrão (conservador).

## Tela / projetor

- **O jogo abriu no monitor errado ou com tamanho errado:**
  1. No Windows, aperte **Win + P** e escolha **Duplicar**. No Linux, espelhe as telas nas configurações de tela.
  2. Feche o jogo (Q Q) e abra de novo: o jogo lê as telas quando inicia.
- **Tela cheia borrada ou cortada no Windows** com escala de 125%/150%: o jogo já se declara "DPI aware"; se acontecer, teste com a escala em 100%.
- O layout se adapta sozinho a 16:9, 16:10 e 4:3.

## Instalação

- **"Python 3.12 não encontrado"** → instale a 3.12 ([INSTALACAO.md](INSTALACAO.md)). Outras versões não servem.
- **O setup para no meio do download** → internet instável; rode o setup de novo, ele continua de onde parou.
- **"Ambiente não encontrado"** → rode o setup (`setup_windows.bat` ou `./setup.sh`) com internet.

## Outros

- **`[ERRO] config.yaml: chave desconhecida ...`** → erro de digitação no config. A mensagem mostra as chaves válidas.
- **Aviso de "GPU lenta/indisponível"** → o jogo continua na CPU sozinho.
