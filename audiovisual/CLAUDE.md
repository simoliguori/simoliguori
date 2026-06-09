# FEEDBACK — opera audiovisiva audio-reattiva autonoma

> Istruzioni operative e di handoff. Questo file è pensato per essere letto da **Claude Code**
> (o un'altra sessione di Claude) per continuare il progetto. La cartella `audiovisual/`
> è **autosufficiente**: spostandola ovunque hai tutto il necessario per iterare.

---

## 0. Handoff rapido (leggi prima questo)

- Tutto il programma è in **un unico file**: `index.html` (HTML+CSS+JS inline, zero dipendenze).
- **DEVE essere servito via HTTP**, non aperto come `file://` e **non dall'anteprima di Cowork**:
  legge i pixel delle immagini (`getImageData`) e fa `fetch`+`decodeAudioData` del brano →
  entrambi bloccati fuori da un vero server. Per testare:
  ```
  cd audiovisual
  python -m http.server 8000      # poi apri http://localhost:8000/
  ```
- C'è un **indicatore di stato audio** in basso a sinistra a schermo (es. `audio: running ·
  granulare ok (181s)` oppure `... · fallback <audio>` / `AUDIO BLOCCATO`): usalo per diagnosi.
- Click su **▶ avvia** è obbligatorio (gesto utente per sbloccare l'AudioContext).
- Per modificare `index.html`: è un file lungo, fai **edit mirati per sezione** (ogni blocco è
  commentato). Verifica sempre la sintassi dopo (`node --check` sullo script estratto).

## 1. Cos'è

Una pagina web autonoma che genera un'opera audiovisiva **diversa a ogni avvio** (PRNG seminato).
Il brano `track.mp3` viene **ri-sintetizzato per sintesi granulare** (grani da punti casuali del
brano, playhead oscillante) e distorto; lo spettro pilota la scena: uno **sfondo pseudo-frattale**
(feedback ricorsivo + simmetrie a specchio + datamosh) con sopra **immagini in chroma-key sporco**
che appaiono, si muovono in modo lo-fi a scatti e lasciano **scie datamosh a blocchi**. Nessun
controllo artistico manuale: tutto si auto-regola e la scena evolve a fasi.

## 2. Struttura della cartella

```
audiovisual/
├── index.html        ← TUTTO il programma (HTML/CSS/JS in un solo file)
├── track.mp3         ← il brano ("perc nuovo"); sostituibile (vedi §7)
├── img/
│   └── img01.jpg … img87.jpg   ← 87 immagini normalizzate (≤1920px, JPG)
├── build_images.py   ← rigenera img/ da immagini sorgente (solo se aggiungi/cambi foto)
└── CLAUDE.md         ← questo file
```
Gli ORIGINALI delle immagini stanno nella cartella padre "hard images" (NON necessari per girare).

## 3. Come si esegue
Vedi §0. In breve: server HTTP + click su “avvia”. Tasti: **Spazio** play/pausa · **F** fullscreen ·
**S** strobo on/off. L'anteprima incorporata non basta (assets fratelli non serviti + sandbox).

## 4. Architettura del codice (`index.html`)

Tutto in una IIFE `(function(){ … })()`. Pezzi chiave:

- **PRNG** `mulberry32(SEED)` con `SEED=Date.now()^random`; helper `RNG()`, `rr(a,b)`, `hash(n)`
  (casualità “tenuta” per step → movimenti a scatti).
- **Canvas offscreen**: `cv` (visibile), `fb` (feedback sfondo), `layer/lx` (temp singolo blob),
  `post/px2` (snapshot per kaleido/datamosh), `ff/ffx` (**feedback dedicato al primo piano** = scie
  datamosh dei blob).
- **`buildChannels(idx)`**: disegna l'immagine in cover e applica il **chroma-key sporco**: trova il
  colore prevalente (istogramma 4-bit) e mette in alpha la distanza da esso, con **rumore per-pixel +
  alpha posterizzato** → silhouette organica frastagliata (niente maschere geometriche). Cache `channelCache` (max 14).

### Audio (importante — qui è dove si è rotto e risistemato)
- `setupAudio()` costruisce: `grainBus(Gain) → shaper(WaveShaper drive) → analyser → destination`.
  **Tutti i nodi vengono messi in `audioKeep[]`** per non farli garbage-collectare (un nodo locale
  GC'd spezza la catena = silenzio: è successo, da non rifare).
- **Sintesi granulare** (`scheduleGrains`/`playGrain`): a ogni frame pianifica grani (lookahead
  ~120ms) leggendo da `audioBuf` (il brano decodificato). `phSec` (playhead) **oscilla** su tutto il
  brano; ogni grano legge `phSec ± scatter`, e con prob. `jumpProb` **salta a un punto a caso**.
  Densità/scatter/jump/size dipendono da `tension`/`releasePulse`. Gli `start` dei grani sono
  clampati a `currentTime+0.005` (envelope udibile).
- **FALLBACK** (`startFallback`): se `fetch`+`decode` non è possibile (anteprima/file/CORS) o non
  arriva entro 2.5s, parte un elemento `<audio loop>` instradato in `grainBus` (suono + reattività)
  o, se la CORS blocca `createMediaElementSource`, in riproduzione diretta. Garantisce suono dove la
  granulare non può caricare. **Nota:** se l'ambiente non serve proprio `track.mp3`, nemmeno il
  fallback può caricarlo.
- **Stato audio a schermo**: in `render()` aggiorno `#phaseTag` con `actx.state` + `audioStatus`
  (decodifica… / granulare ok / fallback / AUDIO BLOCCATO). Diagnostica rapida.
- (Il vecchio bitcrusher `ScriptProcessorNode` è stato **rimosso**: deprecato e fragile. Per
  rimetterlo, meglio un `AudioWorklet` — ma serve un file worklet separato → addio single-file.)
- **`readAudio`**: FFT → 5 bande `bandVal[0..4]` (bassi→alti), beat sui bassi (`beat`), transienti
  via spectral flux → `kick` (scossa datamosh visiva).

### Tensione (accumulo/rilascio) — `updateTension(dt)`
Envelope **auto-oscillante**: `build` (lento, `buildDur` 4–13s) → al culmine `release` (`releasePulse`→1,
`onRelease`). Regola voluta dall'autore per le immagini:
- durante l'**accumulo** le immagini sono **rare** (rate ∝ `1-tension`);
- al **rilascio** → **frenesia** (raffica in `onRelease` + spawn extra finché `releasePulse` decade).
Guida anche la densità/dispersione dei grani.

### Pipeline di `render()` (ordine)
1. `readAudio()` (se playing) → 2. `updateTension` + `scheduleGrains` → status audio → 3. fasi
(`rollScene`/`lerpScene`).
4. **SFONDO**: `drawBed` (immagine piena in crossfade, mai nero) → feedback `fb` (source-over,
decadimento) → velo `soft-light` → `datamoshTear` → `kaleido` (x/y/quad/tile2) → salva in `fb` → `bgGrade`.
5. **PRIMO PIANO** `renderForeground`: scia **datamosh a blocchi** in `ff` (blocchi `sc.fgCols×fgRows`,
traslazione netta lungo il moto medio, salti di blocchi interi + flip → pattern geometrici;
`decayFG` alto = scia lunga/nitida) → `renderLayers` (blob correnti, chroma-key sporco, movimento lo-fi a scatti).
6. strobo → 7. dim → 8. composita `ff` SOPRA tutto (blob nitidi, piena luminosità).

## 5. Mappa dei parametri (dove mettere mano)

| Voglio cambiare… | Dove |
|---|---|
| Durezza/sporco chroma-key | `KEY_D0/KEY_D1` (~r.91) + formula in `buildChannels` (`*1.5`, `(nz-0.5)*85`, soglie posterizzazione) |
| Lunghezza scia datamosh primo piano | `decayFG` (~r.109) — 0.90 corta … 0.97 lunghissima |
| Blocchi datamosh (dimensione/strappi/flip) | `renderForeground` + `sc.fgCols/fgRows` in `rollScene` |
| Movimento lo-fi blob (scatti) | `spawnLayer`: `stepRate, grid, jump, rotStep, vx/vy` |
| Quante immagini insieme | cap in `spawnLayer` (`maxLayers+5`), `channelCache` size |
| Granulare (densità/size/salti/oscillazione) | `scheduleGrains` (`density, scatter, jumpProb, gsize`, `phSec`) + `playGrain` |
| Ritmo accumulo/rilascio + logica spawn | `updateTension` (`buildDur, releaseDur`, formule spawn) |
| Distorsione audio | curva `shaper` in `setupAudio` (waveshaper) |
| Simmetrie sfondo | array `KALEIDO` + `kaleido()` |
| Luminosità/saturazione sfondo | `bgGrade()` + dim finale in `render` |
| Strobo / fotosensibilità | blocco strobo in `render` + checkbox gate |

## 6. Immagini — rigenerare (`build_images.py`)
`img/` è già pronta (87 file). Per cambiare/aggiungere foto:
```
python3 build_images.py /percorso/sorgente     # default ".."
```
Ridimensiona a ≤1920px, ricodifica `img/imgNN.jpg` in ordine alfabetico, gestisce file enormi.
**Poi aggiorna** `const N_IMG = <numero>` in `index.html` (lo script stampa il valore).
Per aggiungere UNA sola immagine senza rinumerare: convertila a `img/img<N+1>.jpg` e incrementa `N_IMG`
(è così che è stata aggiunta `img87.jpg`).

## 7. Audio — sostituire il brano
Rimpiazza `track.mp3` (stesso nome) o cambia `const TRACK`. Caricato via `fetch`+`decodeAudioData`
(qualsiasi formato decodificabile dal browser). La granulare lavora sull'intera durata.

## 8. Integrazione in un'altra pagina web
**iframe** (più semplice):
```html
<iframe src="audiovisual/index.html" style="width:100%;height:100vh;border:0"
        allow="autoplay; fullscreen"></iframe>
```
Serve sito su `http(s)://`; gli assets (`track.mp3`, `img/`) restano relativi a `index.html`.
**Embed nel DOM**: cambia `#stage`/`canvas` da `fixed` ad `absolute` in un wrapper dimensionato e in
`resize()` usa le dimensioni del contenitore. Mantieni il gate (gesto utente per l'audio).

## 9. Gotcha / lezioni apprese
- **Anteprima/file:// = niente assets** → schermo/black + audio muto. Solo HTTP. (È la causa #1 di
  “non sento niente”.)
- **Nodi Web Audio locali → GC → silenzio**: tieni i riferimenti vivi (`audioKeep`).
- **Autoplay**: solo dopo click; per iframe `allow="autoplay"`.
- **Performance**: risoluzione interna capata a 1600px (`maxW` in `resize`). Ogni immagine NUOVA fa un
  `getImageData` (costoso) → cache 14; raffiche enormi = micro-stutter.
- **Fotosensibilità**: strobo/flash, con avviso + kill-switch (gate + tasto S).
- **Modifiche al file**: dopo ogni edit verifica `node --check` (estrai lo `<script>`); il file è
  lungo, evita riscritture monolitiche, preferisci edit per sezione.

## 10. Stato attuale
Fatto: sintesi granulare (playhead oscillante + salti random) con fallback `<audio>` e stato a schermo;
tensione auto-oscillante (accumulo→poche immagini, rilascio→frenesia); waveshaper drive; sfondo
frattale (feedback+kaleido+datamosh); primo piano con chroma-key sporco posterizzato (forma organica),
movimento lo-fi a scatti, scia datamosh a blocchi che genera pattern geometrici; 87 immagini.

Possibili prossimi passi: bitcrusher via **AudioWorklet** (riportare la distorsione granulare lo-fi);
sync dei salti di playhead con i rilasci; reverse/varispeed dei grani; preset/seed in querystring;
modalità “embed” con dimensioni del contenitore; rimuovere l'overlay di stato audio quando l'audio è ok.

## 11. `egg.html` — l'easter egg LIVE del sito (promosso)
`index.html` (in questa cartella) resta la base "pura" di riferimento. **`audiovisual/egg.html` è l'easter
egg ATTIVO**: il Konami in `../index.html` ci reindirizza (`window.location.href='audiovisual/egg.html'`).
La vecchia pagina è conservata in `../egg-old.html`. Editare direttamente `egg.html` (single source).
Differenze rispetto a `index.html`:
- **Tre tracce nel mix**: `track.mp3` (granulare, grainBus 0.85) + `../assets/audio/majin-sonic-cd.mp3`
  (loop egg, **0.85 = stesso volume del granulare**) + `tts.mp3` (voce, `ttsGain` 2.6× + **bitcrusher**).
  Helper `setupExtraTrack(id,vol,dest)`. Catena: grainBus→shaper→**granFilter(lowpass)**→analyser→**limiter**→out.
- **Grain CLOUD continua** (`scheduleGrains`): densità 24–72, grani sempre sovrapposti (no silenzi), pochi salti.
- **Filtro cutoff** (`granFilter`, modulato in `updateTension`): aperto in accumulo, crolla con risonanza sugli scarichi.
- **Bitcrusher TTS** (`makeBitcrusher`): AudioWorklet inline via Blob (bit+sample-rate), fallback WaveShaper. Single-file salvo.
- **Tensione pilotata dal GAIN REALE** (RMS time-domain in `readAudio` → `gainEnv`), non più dal timer.
  `updateTension`: attack lento = accumulo, **caduta del gain = scarico** (`releasePulse`+raffica).
- **Intensità → numero di immagini sovrapposte**: `maxOverlap = 2 + tension*15 + releasePulse*6`
  (cap dei `layers` in `spawnLayer`); spawn rate ∝ intensità.
- **Timeline d'avvio** (`boot`→`armStart`→`startDrop`): loading VHS 3s → **10s di soli sfondi** (silenzio) →
  compare il **prompt centrale** "1 CLICK = 1 DEAD FASCIST" (box nero/rosso, `.show`) che **RESTA finché non
  clicchi** (`PROMPT_DELAY_MS`=10s) → al **click**: sblocca audio + `startDrop` = `playRiser(RISER_S)` **tutto
  white-noise** → `playSubKick()` (**super compresso + delay + riverbero**) + **comparsa glitch** di manifesto/HUD
  → `chaos=granOn=true` = granulare + `playRealTrack()` + majin + tts + immagini + kill.
- **La mia traccia** (`playRealTrack`): forward + **reversed** (`makeReversed`) partono dal **primo kick**
  (`findFirstKick`) in **loop perfetto** (`loopStart=firstKick`, `loopEnd=dur-LOOP_TAIL_S`) → niente fade in/out.
- **TTS**: gain **6.0** (molto alto) + **bitcrusher** + **delay** (feedback) + **riverbero** (`makeIR` convolver)
  + **morph lento/random del pitch** (`ttsPitch*` → `ttsAudio.playbackRate`, in `updateTension`).
- **Click**: raffica di immagini **intorno al cursore** (`spawnLayer(idx,px,py)` + `burstBoost`).
- **Manifesto**: pannello scuro `rgba(0,0,0,.4)` + contorno nero → leggibile (niente più `mix-blend-mode:screen`).
- **Rimossi** i pulsanti strobo/schermo (`#util`); restano `Spazio` (pausa) e l'effetto strobo attivo di default.
- **HUD "1 CLICK = 1 DEAD FASCIST"** (`#fascistHud`): contatore + esplosione (`../assets/img/giphy-explosion.gif`)
  + suoni egg; ogni click entra nell'opera (`kick`+`releasePulse`+`spawnLayer`).
- **Dipende da `../assets/`** (rompe l'autosufficienza della cartella): ok finché vive dentro questo sito.
  Per promuoverla: rinominare in `../egg.html` o puntarci il redirect Konami, e copiare/aggiustare i path assets.
- **Verifica**: l'anteprima headless NON anima (rAF non scatta lì) e non sblocca l'audio →
  testare con `python -m http.server` in un browser vero (clic per sbloccare le 3 tracce).

## 12. Performance & COMPRESSIONE ASSET (regola fissa)
- Lag principale = `buildChannels` (`getImageData` per ogni immagine nuova): ora a **risoluzione ridotta**
  (`KEY_RES=720`) + **cache 40** (niente thrashing) + **cap immagini `maxOverlap≤16`** + risoluzione
  interna `maxW=1280`/DPR≤1.25. Se serve più fluidità: abbassa `KEY_RES`/`maxW` o il cap.
- **REGOLA: comprimere SEMPRE gli asset prima di committarli** (caricamento più rapido). Comandi usati:
  - Immagini → `python` PIL: ridimensiona ≤1280px, `JPEG quality=72 optimize progressive` (in `img/`).
  - Audio → `ffmpeg -c:a libmp3lame`: musica **128k stereo**, voce/TTS **48k mono**.
  - Vale per ogni nuovo asset aggiunto in futuro (immagini, brani, voci).
