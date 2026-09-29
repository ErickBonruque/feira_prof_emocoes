# Jogo das Caretas

Demonstração interativa de **reconhecimento de emoções** para a Feira de Profissões da UTFPR.

A pessoa fica na frente da câmera e precisa fazer três caretas: **feliz, surpresa e triste**. Cada careta só conta se for clara, intensa e mantida por cerca de 1 segundo. Uma rede neural lê a expressão em tempo real, e um **mapa das emoções** no canto da câmera mostra um ponto andando conforme a careta. Ao completar as três, aparece a vitória e depois o **Relatório da IA**: as "fotos" das caretas (guardadas só na memória), a linha do tempo das emoções e o que a IA notou. Um humano confere o relatório (**"A IA acertou?"**) e o operador aperta **ENTER** para chamar o próximo jogador.

A mensagem da demonstração: **a IA faz o relatório; quem decide é sempre uma pessoa.** A tecla **E** abre o modo **"Por dentro da IA"**, que mostra passo a passo o que a rede recebe e o que ela devolve.

- Roda **100% offline**: a internet só é usada uma vez, no setup.
- **Não grava nenhuma imagem**: tudo é processado na memória e descartado.
- Usa apenas **modelos públicos pré-treinados**. Nada vem do laboratório.

---

## Sumário

1. [Como funciona](#como-funciona)
2. [Requisitos](#requisitos)
3. [Instalação passo a passo](#instalação-passo-a-passo)
4. [Como rodar](#como-rodar)
5. [Controles do teclado](#controles-do-teclado)
6. [Como calibrar os limiares](#como-calibrar-os-limiares)
7. [Checklist para o dia do evento](#checklist-para-o-dia-do-evento)
8. [Problemas comuns](#problemas-comuns)
9. [Privacidade](#privacidade)
10. [Estrutura do projeto](#estrutura-do-projeto)
11. [Créditos e licenças](#créditos-e-licenças)

---

## Como funciona

```
webcam ─► captura (thread) ─► YuNet: acha os rostos ─► trava UM jogador
                                                          │
             tela Pygame ◄── jogo (estados) ◄── regras ◄── HSEmotion: 8 emoções + valência + excitação
```

1. **Captura** (`caretas/capture.py`): uma thread lê a câmera e guarda só o quadro mais recente. Se a câmera cair, ela reconecta sozinha.
2. **Detecção de rosto** (`caretas/detection.py`): o YuNet encontra todos os rostos. O jogo **trava no maior e mais centralizado**, depois de ele ficar parado 0,6 s:
   - rostos pequenos (gente passando ao fundo) são ignorados;
   - enquanto o jogador está travado, rostos novos, mesmo maiores, são ignorados;
   - se o jogador sumir por 3 s, a partida reseta.
3. **Emoção** (`caretas/emotion.py`): o rosto do jogador é recortado e endireitado pelos olhos. Uma única inferência do HSEmotion devolve as probabilidades de 8 emoções, mais **valência** (agradável ↔ desagradável) e **excitação** (calmo ↔ agitado).
4. **Regras anti "vitória fácil"** (`caretas/scoring.py`): veja abaixo.
5. **Jogo** (`caretas/game.py`): espera → calibração do rosto neutro → feliz → surpresa → triste → vitória → **relatório**. Tem tempo limite de 60 s por partida; se o tempo acabar, aparece "QUASE!" e o relatório do que deu certo.
6. **Relatório** (`caretas/report.py`): durante a partida, o jogo anota (só em memória) as probabilidades suavizadas, a valência e a excitação de cada quadro. No fim, resume: força e tempo de cada careta, a mais forte, a mais rápida, uma emoção "extra" que a IA viu (medo, raiva, nojo ou desprezo) e a emoção que ficou no topo por mais tempo.
7. **Interface** (`caretas/ui/`): Pygame em tela cheia. Os emojis e animações são desenhados por código, o que garante nitidez em qualquer projetor. O layout se adapta a 16:9 e a 4:3. Os **sons** também são gerados por código (`ui/sound.py`), sem nenhum arquivo baixado.

### O que aparece na tela

| Tela | O que mostra |
|---|---|
| **Jogo** | câmera, a careta pedida, "força da careta", as 3 cartas e, no canto, o **mapa das emoções**: agradável ↔ desagradável × calmo ↔ agitado. O ponto é o jogador; o emoji da careta pedida pulsa no lugar onde ela costuma cair. |
| **Vitória / QUASE!** | comemoração de 5 s (ou 4 s). ENTER pula direto para o relatório. |
| **Relatório da IA** | as 3 fotos das caretas com força e tempo, a **linha do tempo** das 3 emoções (com as fotos no instante em que a IA reconheceu) e, tracejada, a emoção **extra** que a IA também viu (medo, raiva, nojo ou desprezo) com o pico marcado, "o que a IA notou", a **revisão humana** (SIM/NÃO) e o botão **PRÓXIMO JOGADOR**. A resposta vira um carimbo: *CONFERIDO* ou *CORRIGIDO POR UM HUMANO*. O placar "IA ACERTOU X/Y" aparece no topo do jogo. |
| **Por dentro da IA** (tecla E) | 1) o detector acha o rosto e 5 pontos; 2) o recorte 224×224 que a rede realmente recebe; 3) o tempo da rede neural; 4) as 8 emoções ao vivo; 5) o mapa das emoções com rastro. O jogo fica pausado; apertar E de novo volta ao jogo. |

### Regras anti "vitória fácil"

Uma careta só conta quando **as 4 condições** abaixo são verdadeiras ao mesmo tempo, sobre o sinal suavizado:

| Condição | Exemplo (feliz) |
|---|---|
| probabilidade da classe ≥ `min_prob` | P(feliz) ≥ 0,70 |
| subiu pelo menos `min_gain` em relação ao **neutro da própria pessoa** | P(feliz) − neutro ≥ 0,35 |
| o eixo afetivo passou de `axis_min` | valência ≥ +0,30 |
| o eixo mudou pelo menos `axis_gain` em relação ao neutro | valência − neutro ≥ 0,25 |

Para cada emoção, o eixo usado e a direção esperada são estes:

| Emoção | Eixo | Direção |
|---|---|---|
| Feliz | valência | sobe |
| Surpresa | excitação | sobe |
| Triste | valência | desce |

Além das 4 condições, o jogo exige:

- **tempo mínimo**: a expressão precisa se manter por `hold_seconds` (1 s) **e** por `hold_frames` quadros seguidos. Se um quadro falhar, a contagem recomeça do zero;
- **suavização**: uma média móvel exponencial evita que a leitura fique pulando;
- **calibração neutra**: no começo de cada partida, 2,5 s de "fique sério(a)" medem o neutro da pessoa. Se ela já estiver fazendo careta nesse momento, o jogo pede de novo.

Os testes automáticos (`tests/test_game.py`) garantem pelo menos estes casos:

- 60 s de cara neutra **nunca** vence;
- sorrisinho leve não conta;
- expressões rápidas (0,5 s) não contam;
- a careta errada não conta para a emoção pedida;
- uma pessoa cujo neutro já "parece triste" precisa superar o **próprio** neutro.

### Escolhas técnicas

| Parte | Escolha | Por quê |
|---|---|---|
| Detector de rosto | **YuNet** (OpenCV Zoo, 2023mar) | Tem 230 KB, detecção em cerca de 5 a 12 ms na CPU e devolve caixa + 5 pontos do rosto (usados para alinhar). Não traz dependência extra: é o mesmo OpenCV da câmera. Comparação: o MediaPipe é mais pesado e tem a API em transição. O YOLO-face é melhor em rostos pequenos e distantes, que são justamente os que queremos ignorar. |
| Emoção | **HSEmotion `enet_b0_8_va_mtl`** (ONNX, AffectNet) | Dá 8 classes **mais valência e excitação** em uma única inferência, o que permite exigir intensidade, e não só a classe. São 16 MB, com cerca de 4 a 6 ms por rosto na RTX 3050 e cerca de 8 ms na CPU. |
| Execução | **ONNX Runtime GPU (CUDA 13)** com fallback automático para CPU | CUDA e cuDNN vêm como pacotes pip dentro do `.venv`, sem instalar nada no sistema. Se a GPU falhar ou ficar lenta, o jogo passa para a CPU sozinho. |
| Interface | **Pygame (pygame-ce)** em tela cheia | É um processo só: não precisa de navegador, servidor ou permissão de câmera de browser. Tem a menor latência (câmera → tela direto) e mede 59 a 60 FPS no WSLg. |
| Visual | Inspirado no DESIGN.md "The Verge" ([awesome-claude-design](https://github.com/VoltAgent/awesome-claude-design)) | Fundo quase preto (a câmera "salta"), neon menta e ultravioleta, blocos de cor saturada e letras gigantes. É chamativo para foto e legível no projetor. Detalhes em [docs/DESIGN.md](docs/DESIGN.md). |
| Plataforma | **WSL2 (Ubuntu 24.04) + WSLg** | Mesmo ambiente do laboratório. A webcam é repassada do Windows com o `usbipd-win`. |

---

## Requisitos

- Windows 11 com **WSL2 + Ubuntu** (testado: Ubuntu 24.04, WSL 2.6, WSLg).
- **usbipd-win** no Windows, para repassar a webcam ao WSL. Já está instalado neste PC. Em outro PC: `winget install usbipd`.
- Python 3.12 do Ubuntu (`python3`). O setup cria o ambiente sozinho.
- GPU NVIDIA **opcional**: a RTX 3050 é usada se estiver disponível; sem ela, o jogo roda na CPU.
- Uma webcam USB ou integrada.
- Internet **só durante o setup**: cerca de 1,5 GB de pacotes (a maior parte são bibliotecas CUDA) e 17 MB de modelos.

---

## Instalação passo a passo

Todos os comandos rodam no terminal do **Ubuntu (WSL)**, dentro da pasta do projeto:

```bash
cd ~/faculdade/feira_prof_emocoes
```

**1. Setup (com internet, uma vez):**

```bash
./setup.sh
```

O setup:

- cria o `.venv`;
- instala as dependências com versões fixadas;
- baixa os modelos e as fontes, conferindo o SHA-256 de cada arquivo;
- cria o atalho **"Jogo das Caretas"** na Área de Trabalho do Windows;
- roda os testes e a verificação (`--check`).

Pode rodar de novo sem problema: o que já está certo não é baixado outra vez.

**2. Câmera no WSL (uma vez):**

```bash
./scripts/camera_wsl.sh setup   # driver uvcvideo + permissão da câmera (pede a senha do sudo)
./scripts/camera_wsl.sh bind    # compartilha a webcam no Windows (aceite a janela de Administrador)
./scripts/camera_wsl.sh attach  # conecta ao WSL (o start.sh faz isso sozinho depois)
./scripts/camera_wsl.sh status  # confere: deve aparecer /dev/video0
```

O script escolhe a webcam pelo `camera.usb_hardware_id` do `config.yaml`, que aceita várias separadas por vírgula: usa a primeira que estiver conectada. Hoje é `"046d:082d, 1bcf:28c4"` (Logitech C920 e WEMISS CM-A1; a integrada "HD Webcam" é `5986:211b`), então dá para usar qualquer uma das duas sem editar nada. Cada câmera precisa do `bind` uma vez, com ela conectada. Se nenhuma da lista estiver conectada e houver **uma única** webcam, o script usa essa automaticamente. Para descobrir o ID de outra câmera, rode `usbipd list` no Windows.

> Enquanto a câmera está conectada ao WSL, o Windows não consegue usá-la. Para devolvê-la ao Windows: `./scripts/camera_wsl.sh detach`.

**3. Verificação:**

```bash
./start.sh --check
```

Tudo deve aparecer como `[OK]` e a última linha deve ser **TUDO PRONTO!**.

---

## Como rodar

Há duas formas, e as duas usam a configuração do `config.yaml`:

- **Duplo clique** em **"Jogo das Caretas"** na Área de Trabalho do Windows.
- No terminal do WSL: `./start.sh`.

Opções:

```bash
./start.sh                 # tela cheia (padrão do evento)
./start.sh --debug         # já abre com o painel de calibração
./start.sh --windowed      # em janela
./start.sh --camera 1      # outra câmera (/dev/video1)
./start.sh --check         # só verifica modelos, GPU, câmera e tela
.venv/bin/python -m caretas --list-cameras     # lista as câmeras que entregam imagem
.venv/bin/python -m caretas --video teste.mp4  # vídeo em loop no lugar da câmera (só para testes)
```

O `start.sh`:

1. conecta a webcam, com reconexão automática pelo `usbipd --auto-attach`;
2. abre o jogo;
3. **reabre o jogo sozinho** se ele fechar por erro. Para sair de vez, use Q/Esc duas vezes.

---

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
| **C** | Troca de câmera (0 → 1 → 2 → 3) |
| **Q** ou **Esc** (duas vezes) | Sai. O primeiro toque só mostra um aviso, para uma criança não fechar o jogo sem querer |

Resets automáticos:

- o jogador saiu do quadro por mais de 3 s (durante a partida; no relatório ele pode sair à vontade);
- o relatório ficou 90 s na tela sem ninguém apertar ENTER (`game.report_timeout`; 0 = só pelo botão);
- a câmera caiu durante a partida.

Depois da vitória (5 s) ou do "QUASE!" (4 s), o jogo vai sozinho para o relatório e **espera o botão**.

---

## Como calibrar os limiares

Faça a calibração **no local, com a luz do evento**, antes de abrir para o público.

1. Abra com `./start.sh --debug`, ou aperte **D** durante o jogo.
2. O painel da direita mostra:
   - **8 barras** com a probabilidade suavizada de cada emoção. O **traço branco** é a leitura crua do quadro atual; o **traço rosa** é o **pico dos últimos 5 s**;
   - **valência** e **excitação** atuais, com a faixa dos últimos 5 s;
   - o **neutro** medido na calibração, marcado "(PADRÃO)" se a calibração falhou 3 vezes;
   - para **cada emoção**: `PASSA` ou `-----`, a "força" (0 a 100%) e as 4 condições no formato `valor/limiar`, em **verde** (ok) ou **vermelho** (não passou);
   - a contagem "segura: N/12 quadros".
3. **Teste do neutro (o mais importante):** 3 ou mais pessoas, uma de cada vez, ficam 10 s com cara normal, conversando e piscando.
   - **Nenhuma** emoção pode mostrar `PASSA`.
   - Anote os **picos rosa** de FELICIDADE, SURPRESA e TRISTEZA. O `min_prob` de cada emoção deve ficar **pelo menos 0,2 acima** desses picos.
4. **Teste das caretas:** as mesmas pessoas fazem cada careta com vontade. Anote os valores que aparecem quando a careta está boa.
   - O `min_prob` ideal fica entre o pico do neutro + 0,2 e o valor típico da careta − 0,1.
5. Edite o `config.yaml`, no bloco `rules`. Feche (Q Q) e abra o jogo de novo. **Repita o teste do neutro** depois de qualquer ajuste.

| Sintoma | O que mexer (em `rules.<emoção>`) |
|---|---|
| Ninguém consegue a TRISTEZA | Primeiro, ensine: "sobrancelhas para cima no meio, boca para baixo". Se ainda falhar: `min_prob` 0,50 → 0,40, `min_gain` 0,30 → 0,25, `axis_min` 0,10 → 0,05 |
| A SURPRESA confunde com medo | Normal no AffectNet. Peça "boca em O e sobrancelhas lá em cima". Se precisar: `min_prob` 0,60 → 0,50 |
| Está fácil demais | Suba `min_prob`, `min_gain` e/ou `hold_seconds` (1,0 → 1,5) |
| Oscila e perde a contagem no meio | Diminua `emotion.smoothing` (0,40 → 0,30), para mais estabilidade |
| Nunca calibra ("AGORA SEM CARETA...") | Suba `calibration.max_expression` (0,45 → 0,55) |
| Pega gente ao fundo | Suba `detector.min_face_width` (0,12 → 0,16) e/ou `center_weight` |
| O jogador precisa ficar muito perto | Diminua `detector.min_face_width` (0,12 → 0,08) |

> Valores medidos em fotos de teste: sorriso aberto dá P(feliz) de cerca de 1,00 com valência de +0,8 a +0,9. Rosto triste dá P(triste) de cerca de 0,93 com valência de cerca de −0,75. Surpresa dá P(surpresa) de cerca de 0,81 com excitação de cerca de +1,1. Rosto neutro dá P(neutro) de cerca de 0,67. Caretas "de mentira" de crianças costumam ser mais fracas: calibre com gente de verdade.

---

## Checklist para o dia do evento

### Na véspera (com internet)

- [ ] `./setup.sh`: termina com os testes passando.
- [ ] `./scripts/camera_wsl.sh status`: câmera **Shared** ou **Attached**.
- [ ] `./start.sh --check`: **TUDO PRONTO!**
- [ ] Partida completa com a webcam do evento e o projetor, em tela cheia, até o relatório (S/N e ENTER).
- [ ] Som saindo na caixa/TV certa e num volume bom (`audio.volume` no config; **M** muta).
- [ ] Calibração com 3 ou mais pessoas (seção acima).
- [ ] **Teste offline de verdade**: desligue o Wi-Fi e tire o cabo, abra pelo atalho e jogue uma partida.
- [ ] No Windows:
  - Energia: nunca suspender e nunca desligar a tela.
  - Modo **Não perturbe** ligado, para não aparecer notificação no projetor.
  - Pausar atualizações do Windows por uma semana.
- [ ] Carregador na mochila. O notebook na tomada roda mais rápido.

### Chegando no local

- [ ] Ligue o **projetor e a webcam antes** de abrir o jogo.
- [ ] Aperte **Win + P** e escolha **Duplicar**, ou **Somente segunda tela**. Em "Estender", a tela cheia vai para o monitor principal.
- [ ] Posicione a câmera **na altura do rosto das crianças** (cerca de 1,2 m).
- [ ] **Luz de frente** para o jogador, nunca contra janela.
- [ ] Fundo com pouco movimento.
- [ ] Marque com fita, no chão, onde o jogador fica (cerca de 1 m da câmera).
- [ ] Duplo clique em **"Jogo das Caretas"** e faça uma partida de teste.
- [ ] Aperte **D** e faça o teste do neutro rápido com a luz do local. Depois aperte **D** de novo para esconder o painel.
- [ ] Opcional: uma plaquinha "Pode tirar foto da tela! O computador não guarda nenhuma imagem."

### Durante

- Fim de partida → relatório. Pergunte ao jogador **"A IA acertou?"**, aperte **S** ou **N** e depois **ENTER** quando o próximo estiver pronto. Se a pessoa disser "eu estava fingindo!", ótimo gancho: *a IA lê a expressão do rosto, não o que a pessoa sente*, e por isso um humano sempre confere.
- Quer explicar como funciona → **E** (modo "Por dentro da IA"); **E** de novo volta ao jogo.
- Barulho demais ou som atrapalhando o estande vizinho → **M**.
- Algo estranho → **R** reinicia a partida.
- Criança travada numa careta → dê a dica em voz alta. O tempo acaba em 60 s e o jogo volta sozinho.
- Jogo fechou → ele reabre sozinho em 3 s. Se não reabrir, dê duplo clique no atalho.
- Câmera sumiu → espere uns segundos (reconexão automática). Se não voltar: `./scripts/camera_wsl.sh attach`.

### No fim

- **Q** duas vezes para sair.
- `./scripts/camera_wsl.sh detach` devolve a webcam ao Windows.

---

## Problemas comuns

### A câmera não abre ("CÂMERA DESCONECTADA")

1. Rode `./scripts/camera_wsl.sh status`:
   - **câmera não aparece no Windows** → cabo ou porta USB. Veja `usbipd list` no Windows.
   - **Not shared** → `./scripts/camera_wsl.sh bind` (uma vez, como Administrador).
   - **Shared**, sem `/dev/video*` → `./scripts/camera_wsl.sh attach`.
   - **Attached**, sem `/dev/video*` → `./scripts/camera_wsl.sh setup`, que carrega o driver `uvcvideo`.
2. `Permission denied` no `/dev/video0` → `./scripts/camera_wsl.sh setup` e depois feche e abra o terminal. Se não resolver: `wsl --shutdown` no Windows e abra de novo.
3. A câmera está aberta em outro programa do Windows (Teams, Zoom, app Câmera) → feche o programa e rode `attach` de novo.
4. Existem `/dev/video0` e `/dev/video1`: normalmente o `video1` é só metadados. Use o índice **0**, ou aperte **C** para trocar.
5. `.venv/bin/python -m caretas --list-cameras` mostra quais índices entregam imagem.

### O jogo está lento

- Aperte **D** e veja os FPS: a tela deve ficar em cerca de 60. Rode também `./start.sh --check`, que mostra os ms de cada modelo.
- **Câmera a 10-15 FPS no WSL é o limite do repasse USB (`usbipd`), não driver.** Medido em 28/09 com a WEMISS CM-A1 (MJPG): 10 FPS com a exposição automática na luz ambiente e no máximo 15 FPS mesmo com exposição curta, em qualquer resolução (640x480 dá o mesmo). O driver `uvcvideo` negocia 30 FPS normalmente. **Luz forte de frente** ajuda a chegar nos 15. A tela mostra o quadro mais novo da câmera sem esperar a IA e as marcações deslizam a 60 FPS, o que disfarça bem. Para 30 FPS de verdade seria preciso rodar o jogo nativo no Windows.
- O painel mostra **CPU** em vez de GPU → confira o `nvidia-smi` no WSL. Na CPU o jogo funciona, mas usa mais processador.
- Baixe a câmera para `width: 640` e `height: 480`, e o `detector.input_width` para 480.
- O notebook deve estar **na tomada**, no modo de energia "Melhor desempenho", com os outros programas fechados.
- A câmera entrega menos de 15 FPS → pouca luz. Com pouca luz, a webcam aumenta a exposição e perde FPS; ilumine o rosto.

### A detecção está errada

- **Não acha o rosto:**
  - luz fraca ou contra a luz;
  - boné, óculos escuros ou máscara;
  - pessoa muito longe → aproxime, ou diminua `detector.min_face_width`.
- **Travou na pessoa errada:**
  - aperte **R** com só o jogador na frente;
  - suba `center_weight` e `min_face_width`.
- **Troca de jogador sozinho:** isso só acontece se o jogador sumir por mais de 3 s (`detector.lost_seconds`).
- **Emoção errada ou difícil demais:** veja [Como calibrar os limiares](#como-calibrar-os-limiares). A tristeza é a mais difícil de "atuar": ensine a careta.
- **"FIQUE SÉRIO(A)" repete:** a pessoa está rindo na calibração. Peça cara séria; depois de 3 tentativas, o jogo usa um neutro padrão (conservador).

### Tela / projetor

- **O jogo abriu no monitor errado ou com tamanho errado:**
  1. Aperte **Win + P** e escolha **Duplicar**.
  2. Feche o jogo (Q Q) e abra de novo.
  3. Se ainda assim o tamanho estiver errado, rode `wsl --shutdown` no Windows e abra pelo atalho. O WSLg lê as telas quando inicia.
- O layout se adapta sozinho a 16:9, 16:10 e 4:3.

### Outros

- **"Ambiente não encontrado"** → rode `./setup.sh` com internet.
- **`[ERRO] config.yaml: chave desconhecida ...`** → erro de digitação no config. A mensagem mostra as chaves válidas.
- **Aviso de "GPU lenta/indisponível"** → o jogo continua na CPU sozinho.

---

## Privacidade

- **Nenhuma imagem, vídeo ou dado de rosto é gravado em disco.**
  - O código não tem nenhuma chamada de salvar imagem. Confira com `grep -rn "imwrite\|image.save" caretas/`.
  - O log vai só para o console e registra eventos do jogo e FPS, nunca imagens nem valores de emoção.
- **Tudo fica na memória:**
  - a câmera guarda só o quadro mais recente;
  - as 3 "fotos" da vitória e do relatório são recortes pequenos em RAM, **zerados e descartados** quando o operador chama o próximo jogador (ou o relatório volta sozinho). Para desligar as fotos: `ui.victory_snapshots: false`;
  - o relatório guarda só números (probabilidades, valência, excitação, tempos) em RAM, também zerados no reset. Nada disso vai para o log;
  - o modo "Por dentro da IA" mostra o recorte 224×224 na tela, mas ele só existe na memória, quadro a quadro.
- **Nada é enviado para lugar nenhum:**
  - durante a execução, o jogo **bloqueia qualquer conexão de rede** para fora da máquina (`caretas/offline.py`);
  - ele foi testado rodando **sem nenhuma interface de rede** (namespace de rede isolado no Linux), completando uma partida inteira a cerca de 57 FPS.
- As pessoas podem fotografar a tela do projetor com o próprio celular. Isso é escolha delas: o sistema não guarda nada.

---

## Estrutura do projeto

```
feira_prof_emocoes/
├── start.sh              # inicia o jogo (reconecta câmera, reabre se cair)
├── start.bat             # atalho do Windows (gerado pelo setup; cópia na Área de Trabalho)
├── setup.sh              # setup com internet: .venv + deps + modelos + atalho + testes
├── config.yaml           # TODOS os ajustes: câmera, limiares, tempos, textos
├── requirements.txt      # dependências com versões fixadas (requirements-dev.txt: + pytest)
├── models/               # YuNet + HSEmotion (baixados pelo setup, SHA-256 conferido)
├── assets/fonts/         # Anton, Space Grotesk, Space Mono (OFL)
├── scripts/
│   ├── camera_wsl.sh     # webcam Windows -> WSL (usbipd): setup / bind / attach / detach / status
│   └── download_assets.py
├── caretas/
│   ├── __main__.py       # python -m caretas [--debug] [--windowed] [--camera N] [--check] ...
│   ├── app.py            # laço principal, teclado, verificação (--check)
│   ├── config.py         # lê e valida o config.yaml
│   ├── capture.py        # câmera em thread + reconexão
│   ├── detection.py      # YuNet + escolha/travamento do jogador
│   ├── emotion.py        # HSEmotion (ONNX Runtime GPU/CPU), recorte e alinhamento
│   ├── scoring.py        # suavização, calibração neutra, 4 condições, tempo mínimo
│   ├── pipeline.py       # thread de processamento (detecção + emoção)
│   ├── game.py           # máquina de estados do jogo (inclui relatório e revisão humana)
│   ├── report.py         # o que a IA anotou na partida: linha do tempo + resumo (só em memória)
│   ├── offline.py        # bloqueio de rede em tempo de execução
│   ├── manifest.py       # URLs + SHA-256 dos arquivos baixados no setup
│   └── ui/               # renderer (telas), report_view (relatório), lab (por dentro da IA), radar (mapa
│                         # das emoções), smooth (suavização), sound (efeitos sintetizados), emoji, effects, debug, theme
├── tests/                # 53 testes (lógica, relatório, telas e sons; sem câmera): .venv/bin/python -m pytest
└── docs/DESIGN.md        # sistema visual
```

---

## Créditos e licenças

- **YuNet** (detecção de rosto): [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), licença MIT.
- **HSEmotion** (emoção + valência/excitação): A. Savchenko, [face-emotion-recognition](https://github.com/av-savchenko/face-emotion-recognition), código sob Apache-2.0. O modelo foi treinado na AffectNet, cuja licença é de uso acadêmico e não comercial, o que é adequado para esta demonstração educativa.
- **Fontes**: Anton, Space Grotesk e Space Mono, todas sob SIL Open Font License. As licenças estão em `assets/fonts/`.
- **Inspiração visual**: DESIGN.md "The Verge" da coleção [awesome-claude-design](https://github.com/VoltAgent/awesome-claude-design) / getdesign.md. É uma análise independente, sem afiliação com a marca; nenhum logo ou nome da marca é usado no jogo.
