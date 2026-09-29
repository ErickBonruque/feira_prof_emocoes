# Calibração dos limiares

Os limiares de cada careta ficam no bloco `rules` do [`config.yaml`](../config.yaml). O que cada condição significa está em [COMO_FUNCIONA.md › Regras](COMO_FUNCIONA.md#regras-anti-vitória-fácil).

Faça a calibração **no local, com a luz do evento**, antes de abrir para o público.

1. Abra com `--debug` (`start_windows.bat --debug` ou `./start.sh --debug`), ou aperte **D** durante o jogo.
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

## Sintomas e ajustes

| Sintoma | O que mexer (em `rules.<emoção>`, salvo indicação) |
|---|---|
| Ninguém consegue a TRISTEZA | Primeiro, ensine: "sobrancelhas para cima no meio, boca para baixo". Se ainda falhar: `min_prob` 0,50 → 0,40, `min_gain` 0,30 → 0,25, `axis_min` 0,10 → 0,05 |
| A SURPRESA confunde com medo | Normal no AffectNet. Peça "boca em O e sobrancelhas lá em cima". Se precisar: `min_prob` 0,60 → 0,50 |
| Está fácil demais | Suba `min_prob`, `min_gain` e/ou `hold_seconds` (1,0 → 1,5) |
| Oscila e perde a contagem no meio | Diminua `emotion.smoothing` (0,40 → 0,30), para mais estabilidade |
| Nunca calibra ("AGORA SEM CARETA...") | Suba `calibration.max_expression` (0,45 → 0,55) |
| Pega gente ao fundo | Suba `detector.min_face_width` (0,12 → 0,16) e/ou `center_weight` |
| O jogador precisa ficar muito perto | Diminua `detector.min_face_width` (0,12 → 0,08) |

> Valores medidos em fotos de teste: sorriso aberto dá P(feliz) de cerca de 1,00 com valência de +0,8 a +0,9. Rosto triste dá P(triste) de cerca de 0,93 com valência de cerca de −0,75. Surpresa dá P(surpresa) de cerca de 0,81 com excitação de cerca de +1,1. Rosto neutro dá P(neutro) de cerca de 0,67. Caretas "de mentira" de crianças costumam ser mais fracas: calibre com gente de verdade.
