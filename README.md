# Jogo das Caretas

Demonstração interativa de **reconhecimento de emoções** para a Feira de Profissões da UTFPR.

A pessoa fica na frente da câmera e precisa fazer três caretas: **feliz, surpresa e triste**. Uma rede neural lê a expressão em tempo real, e cada careta só conta se for clara, intensa e mantida por cerca de 1 segundo. No fim aparece o **Relatório da IA**, com as "fotos" das caretas, a linha do tempo das emoções e o que a IA notou, e um humano confere: **"A IA acertou?"**

A mensagem da demonstração: **a IA faz o relatório; quem decide é sempre uma pessoa.** A tecla **E** abre o modo **"Por dentro da IA"**, que mostra passo a passo o que a rede recebe e o que ela devolve.

- Roda **100% offline**: a internet só é usada uma vez, na instalação.
- **Não grava nenhuma imagem**: tudo é processado na memória e descartado.
- Usa apenas **modelos públicos pré-treinados**: YuNet (detecção de rosto) e HSEmotion (emoções).
- Funciona no **Windows** e no **Linux**, com GPU NVIDIA ou só com a CPU.

## Como rodar

**Precisa de:** Python **3.12**, uma webcam (a do notebook serve) e internet só na instalação (~1,5 GB).

```bash
git clone https://github.com/ErickBonruque/feira_prof_emocoes.git
cd feira_prof_emocoes
```

(Ou **Code → Download ZIP** aqui no GitHub, extraindo numa pasta sem acentos nem espaços no caminho.)

### Windows

1. Instale o Python 3.12, se ainda não tiver: `winget install Python.Python.3.12`
2. Duplo clique em **`setup_windows.bat`** (uma vez, com internet).
3. Duplo clique no atalho **"Jogo das Caretas (Windows)"** criado na Área de Trabalho, ou em `start_windows.bat`.

### Linux

```bash
./setup.sh     # uma vez, com internet
./start.sh     # para jogar
```

### A câmera não foi encontrada?

É o problema mais comum em um computador novo: o jogo vem configurado para as webcams do evento. Rode `start_windows.bat --list-cameras` (Windows) ou `.venv/bin/python -m caretas --list-cameras` (Linux) e siga o [guia da webcam](docs/WEBCAM.md).

**Q** ou **Esc** duas vezes para sair. Todas as teclas estão no [guia do operador](docs/EVENTO.md#controles-do-teclado).

## Documentação

| Documento | Para quê |
|---|---|
| [Instalação](docs/INSTALACAO.md) | Passo a passo completo no Windows e no Linux, opções de linha de comando, testes |
| [Webcam](docs/WEBCAM.md) | Fazer o jogo achar a sua câmera e resolver problemas de imagem |
| [Guia do operador](docs/EVENTO.md) | Teclas, checklist da véspera e do dia, o que fazer durante a feira |
| [Calibração](docs/CALIBRACAO.md) | Ajustar a dificuldade de cada careta com a luz do local |
| [Como funciona](docs/COMO_FUNCIONA.md) | Arquitetura, regras anti "vitória fácil", escolhas técnicas, estrutura do código |
| [Problemas comuns](docs/PROBLEMAS.md) | Lentidão, detecção errada, projetor, erros de instalação |
| [Privacidade](docs/PRIVACIDADE.md) | O que fica na memória e por que nada é gravado ou enviado |
| [Design](docs/DESIGN.md) | Sistema visual (cores, fontes, layout) |

Todos os ajustes (câmera, limiares, tempos, textos) ficam no [`config.yaml`](config.yaml), comentado linha a linha.

## Créditos e licenças

- **YuNet** (detecção de rosto): [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), licença MIT.
- **HSEmotion** (emoção + valência/excitação): A. Savchenko, [face-emotion-recognition](https://github.com/av-savchenko/face-emotion-recognition), código sob Apache-2.0. O modelo foi treinado na AffectNet, cuja licença é de uso acadêmico e não comercial, o que é adequado para esta demonstração educativa.
- **Fontes**: Anton, Space Grotesk e Space Mono, todas sob SIL Open Font License. As licenças estão em `assets/fonts/`.
- **Inspiração visual**: DESIGN.md "The Verge" da coleção [getdesign.md](https://getdesign.md). É uma análise independente, sem afiliação com a marca; nenhum logo ou nome da marca é usado no jogo.
