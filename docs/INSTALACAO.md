# Instalação

O jogo roda no **Windows** e no **Linux**. Nos dois casos:

- **Python 3.12.** Outras versões (3.11, 3.13) não servem: as dependências foram fixadas e testadas na 3.12.
- Uma webcam (a do notebook serve). Para configurar: [WEBCAM.md](WEBCAM.md).
- Internet **só durante o setup**: cerca de 1,5 GB de pacotes (a maior parte são bibliotecas CUDA) e 17 MB de modelos. Reserve uns 3 GB livres.
- GPU NVIDIA **opcional**: é usada se estiver disponível; sem ela, o jogo roda na CPU sozinho.

O setup cria um ambiente isolado (`.venv`) dentro da pasta do projeto e não mexe no Python do sistema. Pode rodar o setup de novo quantas vezes quiser: o que já está certo não é baixado outra vez.

## Baixar o projeto

```bash
git clone https://github.com/ErickBonruque/feira_prof_emocoes.git
cd feira_prof_emocoes
```

Sem o Git: botão verde **Code → Download ZIP** no GitHub e extraia numa pasta **sem acentos nem espaços no caminho** (ex.: `C:\jogos\feira_prof_emocoes`).

---

## Windows

Testado no Windows 11; deve funcionar no Windows 10 64 bits.

**1. Python 3.12** (se ainda não tiver):

```bat
winget install Python.Python.3.12
```

Ou baixe a 3.12 em [python.org](https://www.python.org/downloads/). O setup também acha o Python 3.12 do Miniconda/Anaconda.

**2. Setup (com internet, uma vez):** duplo clique em **`setup_windows.bat`**. Ele:

- acha um Python 3.12 (lançador `py`, Miniconda ou python.org) e cria o `.venv`;
- instala as versões fixadas do `requirements.txt` (inclusive `onnxruntime-gpu`, com CUDA/cuDNN em pacotes pip);
- baixa os modelos e as fontes, conferindo o SHA-256 de cada arquivo;
- cria o atalho **"Jogo das Caretas (Windows)"** na Área de Trabalho;
- roda os testes e a verificação (`--check`).

Se no fim só a linha da câmera falhar, veja [WEBCAM.md](WEBCAM.md): quase sempre é só dizer ao jogo qual é a sua câmera.

**3. Jogar:** duplo clique no atalho ou em `start_windows.bat`. Se o jogo fechar por erro, ele reabre sozinho em 3 s. Para sair de vez: **Q** ou **Esc** duas vezes.

```bat
start_windows.bat                  :: tela cheia (padrão do evento)
start_windows.bat --debug          :: já abre com o painel de calibração
start_windows.bat --windowed       :: em janela
start_windows.bat --camera 0       :: usa a câmera de índice 0, ignorando a lista do config
start_windows.bat --list-cameras   :: mostra as câmeras encontradas e qual o jogo usa
start_windows.bat --check          :: só verifica modelos, GPU, câmera e tela
```

---

## Linux

Testado no Ubuntu 24.04. Precisa de uma sessão gráfica (X11 ou Wayland).

**1. Python 3.12 com venv.** No Ubuntu 24.04 já vem o 3.12; o setup instala o `python3-venv` se faltar (pede a senha do sudo). Em outras distribuições, instale o Python 3.12 com o módulo `venv` pelo gerenciador de pacotes.

**2. Setup (com internet, uma vez):**

```bash
./setup.sh
```

Faz o mesmo que o setup do Windows: `.venv`, dependências fixadas, modelos com SHA-256, testes e `--check`.

**3. Jogar:**

```bash
./start.sh                 # tela cheia (padrão do evento)
./start.sh --debug         # já abre com o painel de calibração
./start.sh --windowed      # em janela
./start.sh --camera 1      # outra câmera (/dev/video1)
./start.sh --check         # só verifica modelos, GPU, câmera e tela
.venv/bin/python -m caretas --list-cameras     # lista as câmeras que entregam imagem
.venv/bin/python -m caretas --video teste.mp4  # vídeo em loop no lugar da câmera (só para testes)
```

Como no Windows, o `start.sh` reabre o jogo sozinho se ele fechar por erro; Q/Esc duas vezes sai.

**GPU no Linux:** precisa do driver NVIDIA proprietário instalado (`nvidia-smi` deve funcionar). CUDA e cuDNN vêm como pacotes pip, então não é preciso instalar o CUDA Toolkit.

---

## Testes

```bat
.venv\Scripts\python.exe -m pytest -q     :: Windows
```

```bash
.venv/bin/python -m pytest -q             # Linux
```

Os testes cobrem a lógica do jogo, o relatório, as telas e os sons, sem precisar de câmera.
