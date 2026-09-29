# Como funciona

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

## O que aparece na tela

| Tela | O que mostra |
|---|---|
| **Jogo** | câmera, a careta pedida, "força da careta", as 3 cartas e, no canto, o **mapa das emoções**: agradável ↔ desagradável × calmo ↔ agitado. O ponto é o jogador; o emoji da careta pedida pulsa no lugar onde ela costuma cair. |
| **Vitória / QUASE!** | comemoração de 5 s (ou 4 s). ENTER pula direto para o relatório. |
| **Relatório da IA** | as 3 fotos das caretas com força e tempo, a **linha do tempo** das 3 emoções (com as fotos no instante em que a IA reconheceu) e, tracejada, a emoção **extra** que a IA também viu (medo, raiva, nojo ou desprezo) com o pico marcado, "o que a IA notou", a **revisão humana** (SIM/NÃO) e o botão **PRÓXIMO JOGADOR**. A resposta vira um carimbo: *CONFERIDO* ou *CORRIGIDO POR UM HUMANO*. O placar "IA ACERTOU X/Y" aparece no topo do jogo. |
| **Por dentro da IA** (tecla E) | 1) o detector acha o rosto e 5 pontos; 2) o recorte 224×224 que a rede realmente recebe; 3) o tempo da rede neural; 4) as 8 emoções ao vivo; 5) o mapa das emoções com rastro. O jogo fica pausado; apertar E de novo volta ao jogo. |

## Regras anti "vitória fácil"

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

Como ajustar os limiares no local: [CALIBRACAO.md](CALIBRACAO.md).

## Escolhas técnicas

| Parte | Escolha | Por quê |
|---|---|---|
| Detector de rosto | **YuNet** (OpenCV Zoo, 2023mar) | Tem 230 KB, detecção em cerca de 5 a 12 ms na CPU e devolve caixa + 5 pontos do rosto (usados para alinhar). Não traz dependência extra: é o mesmo OpenCV da câmera. Comparação: o MediaPipe é mais pesado e tem a API em transição. O YOLO-face é melhor em rostos pequenos e distantes, que são justamente os que queremos ignorar. |
| Emoção | **HSEmotion `enet_b0_8_va_mtl`** (ONNX, AffectNet) | Dá 8 classes **mais valência e excitação** em uma única inferência, o que permite exigir intensidade, e não só a classe. São 16 MB, com cerca de 4 a 6 ms por rosto numa RTX 3050 e cerca de 8 ms na CPU. |
| Execução | **ONNX Runtime GPU (CUDA 13)** com fallback automático para CPU | CUDA e cuDNN vêm como pacotes pip dentro do `.venv`, sem instalar nada no sistema. Se a GPU falhar ou ficar lenta, o jogo passa para a CPU sozinho. |
| Interface | **Pygame (pygame-ce)** em tela cheia | É um processo só: não precisa de navegador, servidor ou permissão de câmera de browser. Tem a menor latência (câmera → tela direto) e roda a 60 FPS. |
| Câmera | **DirectShow** no Windows, **V4L2** no Linux | No Windows, a câmera é achada pelo VID:PID, porque os índices mudam. Detalhes em [WEBCAM.md](WEBCAM.md#detalhes-técnicos-windows). |
| Visual | Inspirado no DESIGN.md "The Verge" ([getdesign.md](https://getdesign.md)) | Fundo quase preto (a câmera "salta"), neon menta e ultravioleta, blocos de cor saturada e letras gigantes. É chamativo para foto e legível no projetor. Detalhes em [DESIGN.md](DESIGN.md). |

## Estrutura do projeto

```
feira_prof_emocoes/
├── setup_windows.bat     # setup no Windows: .venv + deps + modelos + atalho + testes
├── start_windows.bat     # inicia o jogo no Windows (reabre se cair)
├── setup.sh              # setup no Linux: .venv + deps + modelos + testes
├── start.sh              # inicia o jogo no Linux (reabre se cair)
├── config.yaml           # TODOS os ajustes: câmera, limiares, tempos, textos
├── requirements.txt      # dependências com versões fixadas (requirements-dev.txt: + pytest)
├── models/               # YuNet + HSEmotion (baixados pelo setup, SHA-256 conferido)
├── assets/fonts/         # Anton, Space Grotesk, Space Mono (OFL)
├── scripts/
│   └── download_assets.py
├── caretas/
│   ├── __main__.py       # python -m caretas [--debug] [--windowed] [--camera N] [--check] ...
│   ├── app.py            # laço principal, teclado, verificação (--check)
│   ├── config.py         # lê e valida o config.yaml
│   ├── capture.py        # câmera em thread + reconexão
│   ├── win_camera.py     # Windows: acha a câmera pelo VID:PID no DirectShow (só ctypes)
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
├── tests/                # testes de lógica, relatório, telas e sons (sem câmera)
└── docs/                 # esta documentação
```
