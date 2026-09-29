# Sistema visual: Jogo das Caretas

Adaptado do DESIGN.md "The Verge" (coleção [getdesign.md](https://getdesign.md)). Instalado com `npx getdesign@latest add theverge` e reinterpretado para **projetor + crianças + foto de celular**. Os tokens estão implementados em `caretas/ui/theme.py`.

## Por que este estilo

- **Fundo quase preto** (`#131313`): a imagem da câmera vira o centro e salta aos olhos, tanto na foto quanto no projetor.
- **Acentos "fita de perigo"** em menta `#3cffd0` e ultravioleta `#5200ff`, mais **blocos de cor saturada**. Parece pôster de festa, bom para foto de Instagram.
- **Letras gigantes** (Anton, substituta livre da Manuka), legíveis do fundo da sala.
- **Sem gradiente e sem sombra**: o contraste vem de blocos sólidos. Texto sobre a câmera **sempre** fica dentro de um bloco colorido, e nunca "solto" sobre a imagem.

## Tokens

| Token | Cor | Uso |
|---|---|---|
| canvas | `#131313` | fundo de tudo |
| slate | `#2d2d2d` | superfícies secundárias, trilho de barras |
| mint | `#3cffd0` | acento principal, moldura da câmera, SURPRESA |
| ultraviolet | `#5200ff` | acento secundário, TRISTE |
| yellow | `#ffde00` | FELIZ, tela "QUASE!" |
| pink / orange | `#ff3d8b` / `#ff6a00` | bochechas, confete, alertas ("CADÊ VOCÊ?") |

Tipografia:

| Uso | Fonte |
|---|---|
| display | **Anton**, só em tamanhos grandes |
| interface | **Space Grotesk** Bold/Medium |
| rótulos | **Space Mono** Bold, sempre em CAIXA ALTA com espaçamento de cerca de 12% do tamanho |

Todas as medidas usam a unidade `u` (1 u = 1 px em 1920x1080).

## Componentes

- **Moldura da câmera**: cantos de 34 u, borda de 4 u na **cor da emoção atual**.
- **Cantoneiras de visor** em volta do rosto do jogador, com a pílula "VOCÊ".
- **Banner** (base da câmera): bloco da cor da emoção, com emoji, título (Anton), dica (Space Grotesk) e o medidor "FORÇA DA CARETA". Um anel preto em volta do emoji mostra o "SEGURA AÍ!".
- **Cards das caretas**: contorno colorido quando pendente; preenchido quando é a atual ou já foi feita. Quando feita, mostra a miniatura redonda do jogador, um adesivo de emoji e um ✓.
- **Carimbo** entre caretas ("QUE SORRISÃO!", "UAU!", "QUE DRAMA!"): gira e cresce com *ease-out-back*, acompanhado de flash de "foto" e confete.
- **Vitória**: faixas listradas menta/ultravioleta, "VOCÊ VENCEU!" gigante e 3 polaroides tortas com fita adesiva na cor da emoção.
- **Letreiro** no rodapé: frase educativa rolando dentro de uma pílula sobre fita listrada.
- **Mapa das emoções** (canto da câmera): cartão escuro com borda na cor da emoção lida, "A IA VÊ: …" no topo e um radar (anéis + cruz em slate). Os emojis marcam onde cada careta cai; o da careta pedida pulsa dentro de um anel colorido. O ponto do jogador desliza com rastro que some no fundo. Em telas pequenas, os rótulos dos eixos somem.
- **Relatório da IA**: uma "ficha" por careta (bloco da cor da emoção, foto com cantos arredondados, adesivo de emoji, ✓, "FORÇA 95% • 2,5 S"); careta não feita vira contorno com emoji apagado e "A IA NÃO VIU". Linha do tempo em cartão escuro, com linhas grossas (triste usa ultravioleta clareado `#966eff` para ter contraste no escuro), faixa "NEUTRO" da calibração e as fotos redondas no instante do reconhecimento. A emoção extra ("a IA também viu") entra tracejada, por baixo, na cor da sua classe (`theme.CLASS_COLORS`), com uma etiqueta no pico que desvia das fotos; o ícone "8" dos achados usa a mesma cor. Entrada em cascata: fichas com *ease-out-back*, linhas "imprimindo" da esquerda para a direita, achados deslizando.
- **Revisão humana**: botões grandes SIM (menta) e NÃO (laranja) com tecla desenhada; o escolhido ganha borda branca e ✓, o outro vira slate. A resposta vira **carimbo** girado (-9°) sobre o gráfico, nunca sobre as fotos: CONFERIDO (menta) ou CORRIGIDO (amarelo) POR UM HUMANO.
- **Botão PRÓXIMO JOGADOR**: pílula branca com tecla ENTER e seta; fica menta e "respira" depois da revisão.
- **Por dentro da IA**: câmera com os 5 pontos do rosto ligados em menta + grade 2×2 de etapas numeradas (círculo menta com número em Anton). No 4:3, a etapa "rede neural" vira texto na pílula da câmera.
- **Sons**: sintetizados (numpy), curtos e "de desenho animado": bip ao travar, tic na contagem, arpejo ao começar, notas subindo enquanto segura a careta, obturador + sininho ao completar, fanfarra, trombone triste no "QUASE!", impressora no relatório, carimbo na revisão.

## Layouts

| Proporção | Câmera | Caretas |
|---|---|---|
| **wide** (≥ 1,45:1) | à esquerda, 64% da largura | 3 cards empilhados à direita |
| **stacked** (projetor 4:3) | em cima | 3 cards lado a lado embaixo |
