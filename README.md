# 📻 Émetteur Radio SSTV & SDR via RAMDAC VGA (GPU DDS)

> **Projet expérimental de radio logicielle (SDR) autonome détournant le convertisseur numérique-analogique (RAMDAC) d'une carte graphique NVIDIA GeForce pour émettre en direct des images SSTV (Martin 1) en bande HF (20m / 14.230 MHz USB).**

Ce guide documente l'ensemble de l'architecture, le protocole expérimental, les principes mathématiques sous-jacents, ainsi que **tous les écueils techniques rencontrés et leurs solutions** pour permettre une reproduction parfaite du banc d'essai.

---

## 📑 Table des Matières

1. [Avertissements Légaux et Réglementation](#-avertissements-légaux-et-réglementation)
2. [Principe de Fonctionnement](#-principe-de-fonctionnement)
3. [Matériel et Câblage Recommandés](#-matériel-et-câblage-recommandés)
4. [Installation et Prérequis](#-installation-et-prérequis)
5. [Guide Pratique Pas-à-Pas](#-guide-pratique-pas-à-pas)
   - [Étape 1 : Configuration de la sortie vidéo X11 / Nouveau](#étape-1--configuration-de-la-sortie-vidéo-x11--nouveau)
   - [Étape 2 : Calibration de la porteuse RF (CW)](#étape-2--calibration-de-la-porteuse-rf-cw)
   - [Étape 3 : Émission et Décodage SSTV Automatisé](#étape-3--émission-et-décodage-sstv-automatisé)
6. [Architecture Détaillée de la Solution](#-architecture-détaillée-de-la-solution)
   - [Pourquoi cette architecture ?](#1-pourquoi-cette-architecture--genèse-des-choix-de-conception)
   - [Que fait le script setup (setup_display.sh) ?](#2-que-fait-le-script-de-configuration-système-setup_displaysh-)
   - [Que fait le script Python (vga_sstv.py) ?](#3-que-fait-le-script-python-principal-vga_sstvpy-)
   - [Que contient la texture VRAM ?](#4-que-contient-la-texture-vram-)
   - [Que fait le GPU Shader (Fragment Shader GLSL) ?](#5-que-fait-le-gpu-shader-fragment-shader-glsl-)
7. [Les 7 Grands Écueils Techniques et Leurs Solutions](#-les-7-grands-écueils-techniques-et-leurs-solutions)
8. [Fichiers et Organisation du Projet](#-fichiers-et-organisation-du-projet)
9. [Résultats Expérimentaux et Performances](#-résultats-expérimentaux-et-performances)

---

## ⚠️ Avertissements Légaux et Réglementation

> [!CAUTION]
> **CADRE LÉGAL ET SÉCURITÉ MATÉRIELLE (RÉGLEMENTATION ANFR / ITU-R)**
>
> 1. **INTERDICTION D'ÉMETTRE SUR ANTENNE SANS LICENCE :**
>    L'émission dans les bandes radioamateurs (ex: 20m / 14.230 MHz, 6m / 50.100 MHz) est strictement réservée aux opérateurs titulaires d'une **licence radioamateur officielle avec indicatif** (ex: F4JXQ).
>
> 2. **UTILISATION RECOMMANDÉE D'UNE CHARGE FICTIVE OU COUPLAGE LOCAL :**
>    Pour les tests en laboratoire, privilégiez une **charge fictive 50 $\Omega$ fermée** ou un atténuateur de puissance ($-30\text{ dB}$ à $-40\text{ dB}$) raccordé à votre récepteur SDR. En couplage d'air libre sans atténuateur direct, utilisez uniquement deux brins filaires courts (15 cm) à proximité immédiate du récepteur, sans aucune amplification.
>
> 3. **PURETÉ SPECTRALE ET FILTRAGE PASSE-BAS :**
>    La conversion numérique-analogique d'un RAMDAC génère des marches d'escalier et des raies harmoniques vidéo ($f_H \approx 67.5\text{ kHz}$). Si une émission en l'air est effectuée par un radioamateur licencié, un **filtre passe-bas d'ordre 5 ou 7 (type Chebyshev ou Butterworth)** est indispensable pour couper au-delà de 15 MHz.

---

## 🧠 Principe de Fonctionnement

Un écran VGA analogique est piloté par un **RAMDAC** (triple DAC 8-bit rouge/vert/bleu cadencé par un oscillateur quartz matériel, typiquement à **148.50 MHz** pour du 1080p @ 60Hz, ou **285.50 MHz** pour du 1080p @ 120Hz).

En écrivant un **Fragment Shader OpenGL (GLSL)** exécuté en plein écran par les unités de calcul du GPU, nous calculons pour chaque pixel la valeur instantanée d'une onde radiofréquence :
- Le balayage vidéo horizontal et vertical transforme la succession spatiale des pixels à l'écran en un flux temporel d'échantillons analogiques sur la broche physique **Rouge (Broche 1)** du connecteur VGA.
- La porteuse radio à **14.230 MHz** est synthétisée par **synthèse numérique directe (DDS 32 bits)** dans le shader.
- Le signal audio SSTV (Martin 1) est modulé en **bande latérale supérieure pure (BLU / USB)** via un mélangeur en quadrature cartésien :
  $$\text{RF}(t) = I(t)\cos(\theta_c(t)) - Q(t)\sin(\theta_c(t))$$
  où $I(t)$ et $Q(t)$ sont les composantes analytiques en bande de base de l'audio SSTV pré-calculé, chargées en VRAM dans une texture float16.

```
[ GPU NVIDIA GT 630 ]
  ├── Cœurs CUDA / Fragment Shader (DDS 32-bit + Mélangeur I/Q USB)
  └── RAMDAC Vidéo (148.50 MSPS / 8-bit DAC)
         ├── Broche 1 VGA (Rouge) ────────► Signal RF 14.230 MHz USB
         └── Broche 6 VGA (GND)   ────────► Masse RF
```

---

## 🛠️ Matériel et Câblage Recommandés

### Matériel Testé avec Succès :
- **GPU Émetteur** : NVIDIA GeForce GT 630 (architecture Fermi NVC1 / Kepler GK208) sous Linux avec le pilote open-source `nouveau`.
- **Récepteur SDR** : SDRplay RSP1 (14 bits, 250 kSps à 2 MSps) ou clé RTL-SDR v3/v4.
- **Liaison physique** : Deux petits câbles filaires de 15 cm branchés sur la broche 1 (Rouge) et la broche 6 (GND) du connecteur VGA de la carte graphique, placés à 20-30 cm de l'antenne télescopique du SDRplay.

### Brochage du connecteur VGA (DE-15) :
- **Broche 1** : Signal Rouge (Sortie RF $0.0\text{V} - 0.7\text{V}$, impédance source $75\,\Omega$)
- **Broche 6** : Masse Rouge (GND RF)
- *(Optionnel)* : Des résistances de $75\,\Omega$ vers la masse sur les broches 2 (Vert) et 3 (Bleu) aident la carte à détecter la présence d'une charge vidéo si le pilote refuse d'activer la sortie.

---

## 📦 Installation et Prérequis

Sur la machine émettrice et réceptrice (Debian / Ubuntu / Raspberry Pi) :

```bash
# 1. Dépendances système
sudo apt update
sudo apt install -y python3-pip python3-venv x11-xserver-utils libglfw3 libsoapysdr-dev soapysdr-module-all qsstv

# 2. Cloner et installer l'environnement Python
git clone https://github.com/votre-depot/vga-hamradio.git
cd vga-hamradio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Compilation de l'outil de capture SDRplay haute performance C++ (optionnel mais recommandé)
g++ -O3 capture_iq.cpp -lSoapySDR -o capture_iq
```

---

## 🚀 Guide Pratique Pas-à-Pas

### Étape 1 : Configuration de la sortie vidéo X11 / Nouveau
Le pilote Nouveau nécessite que la sortie analogique soit physiquement marquée comme active (`connected`) et qu'un CRTC lui soit alloué :

```bash
# Si le connecteur est vu comme 'disconnected' par le noyau :
echo on | sudo tee /sys/class/drm/card0-VGA-1/status

# Application du mode 1080p @ 60Hz strict (Pixel Clock: 148.50 MHz)
DISPLAY=:0 ./setup_display.sh -o VGA-1 -r 60
```
Le script configure la correction gamma à 1.0 (linéarité stricte du DAC) et désactive la mise en veille DPMS.

---

### Étape 2 : Calibration de la porteuse RF (CW)
L'oscillateur quartz de votre carte graphique présente une légère dérive d'usine (généralement entre $+1\text{ ppm}$ et $+5\text{ ppm}$, soit $+20$ à $+50\text{ Hz}$ à $14.230\text{ MHz}$).

1. Ouvrez votre logiciel SDR (**Gqrx**, **SDR#**, ou **CubicSDR**) centré sur **14.230000 MHz** en mode **CW** ou **USB**.
2. Lancez une émission de porteuse pure de calibration :
   ```bash
   DISPLAY=:0 python3 vga_sstv.py --cw -f 14.230e6 --fullscreen --duration 15.0
   ```
3. Relevez la fréquence exacte du pic (sur notre banc : **14.230038 MHz**, soit $+38\text{ Hz}$ de décalage). Notez cette valeur pour le décodeur.

---

### Étape 3 : Émission et Décodage SSTV Automatisé

1. Générez la mire d'essai officielle haute visibilité :
   ```bash
   # Utilisation par défaut (F4JXQ sur 14.230 MHz USB, sortie mire_f4jxq.png) :
   python3 generate_test_card.py

   # Ou personnalisée avec votre propre indicatif et bande/fréquence :
   python3 generate_test_card.py ON4ABC -f 7.171 -m LSB
   ```
   *(Génère automatiquement `mire_<indicatif>.png` en 320x256 avec barres SMPTE, dégradé de gris, indicatif contrasté et détection automatique de la bande amateur).*

2. Exécutez le script d'orchestration end-to-end :
   ```bash
   python3 full_sstv_transmission_and_decode.py
   ```
   Ce script :
   - Démarre la capture SDRplay en arrière-plan à 250 kSps sur $14.220\text{ MHz}$.
   - Lance la transmission SSTV GPU sur la machine émettrice via SSH.
   - À la fin des 125 secondes, démodule le flux en bande de base USB, extrait l'audio dans [`sstv_audio_demod.wav`](./sstv_audio_demod.wav), décode les 256 lignes et génère l'image finale [`image_recue.png`](./image_recue.png).

---

### Étape 4 : Décodage avec QSSTV et Robot36

Le signal audio produit est 100 % conforme aux standards radioamateurs internationaux :

- **Avec QSSTV (Linux PC)** :
  1. Lancez `qsstv`.
  2. Allez dans **File ➔ Play audio file** et sélectionnez [`sstv_audio_demod.wav`](./sstv_audio_demod.wav).
  3. QSSTV détecte automatiquement le mode Martin 1, synchronise l'en-tête VIS et affiche l'image reçue en couleur sans aucun décalage.
- **Avec Robot36 (Smartphone Android)** :
  1. Ouvrez l'application **Robot36** sur votre smartphone.
  2. Lancez la transmission ou jouez le fichier audio démodulé (`paplay sstv_audio_demod.wav`).
  3. L'application se synchronise automatiquement grâce au préambule VOX et dessine la mire ligne par ligne.

---

## 🏛️ Architecture Détaillée de la Solution

Pour transformer une simple carte graphique grand public en émetteur radio BLU (USB) capable de transmettre 115 secondes d'image couleur SSTV à 150 millions d'échantillons par seconde, une architecture hybride **CPU (Pré-calcul haute fidélité) + GPU (Synthèse et mélange temps réel)** a été conçue.

### 1. Pourquoi cette architecture ? (Genèse des choix de conception)

Lorsqu'on cherche à générer un signal radio à $14.230\text{ MHz}$ :
1. **L'impossibilité du CPU seul :** Un processeur généraliste sous Linux ne peut pas débiter un flux d'échantillons analogiques continu à 150 MSPS sans gigue. L'ordonnanceur de l'OS (changements de contexte, gestion des interruptions, cache misses) introduit des micro-coupures de quelques microsecondes qui détruiraient irrémédiablement la phase de l'onde radio.
2. **La puissance du RAMDAC matériel :** La carte graphique possède son propre convertisseur numérique-analogique (RAMDAC), cadencé par un oscillateur quartz matériel indépendant ($148.50\text{ MHz}$ ou $285.50\text{ MHz}$). Une fois le flux d'affichage lancé, le RAMDAC lit la mémoire vidéo et génère le signal analogique de manière strictement ininterrompue, insensible à la charge CPU de l'OS.
3. **Le découpage des responsabilités (CPU vs GPU) :**
   - **Tenter de tout calculer dans le GPU Shader** en temps réel (déroulement des lignes, alternance des couleurs, porches de synchronisation, décodage des pixels) imposerait une logique conditionnelle lourde dans chaque thread de fragment, entraînant des divergences de branchement (*branch divergence*) et des pertes de précision numérique sur les 115 secondes.
   - **Solution adoptée :** Le **CPU** pré-calcule le signal audio SSTV complet en bande de base avec une précision mathématique maximale (64 bits), puis le **GPU** prend le relais pour convertir ce signal audio en RF à 14.230 MHz au rythme de son horloge matérielle.

```
+-----------------------------------------------------------------------------+
|                                CPU (PYTHON)                                 |
|  1. Mire source 320x256 (Image PIL)                                         |
|  2. Encodage Martin 1 : VOX (1900Hz) + VIS (Code 44) + Lignes (V, B, R)     |
|  3. Intégration de phase en float64 modulo 1.0 (zéro gigue)                |
|  4. Génération quadrature : I(t) = cos(φ), Q(t) = sin(φ)                    |
+--------------------------------------+--------------------------------------+
                                       |
                   Transfert VRAM (Texture 2D RG16F)
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                           GPU (FRAGMENT SHADER GLSL)                        |
|  1. gl_FragCoord.xy  ──►  sample_in_frame (intégre porches H_total/V_total)  |
|  2. DDS 32-bit       ──►  Porteuse RF pure : θ_c = frame_phase + n*Δθ       |
|  3. Texture Fetch    ──►  Interpolation sous-échantillon I(t) et Q(t)       |
|  4. Mélangeur USB    ──►  RF(t) = I(t)*cos(θ_c) - Q(t)*sin(θ_c)             |
|  5. Dither temporel  ──►  DAC = 0.5 + 0.5*RF + dither(u_frame_phase)        |
+--------------------------------------+--------------------------------------+
                                       |
                           Balayage RAMDAC matériel
                                       v
         [ Sortie Physique : Broche 1 VGA (Rouge) + Broche 6 (Masse) ]
                   ──► Émission RF 14.230 MHz USB en l'air ──►
```

---

### 2. Que fait le script de configuration système (`setup_display.sh`) ?

Le pilote graphique Linux (`nouveau` ou `nvidia`) et le serveur X11 sont conçus pour afficher un bureau sur un écran, pas pour servir d'émetteur radio. Le script [`setup_display.sh`](./setup_display.sh) prépare l'environnement matériel :
- **Activation forcée du port VGA :** Si aucun écran n'est branché (ou seulement 2 fils), le noyau Linux désactive le port (`disconnected`). Le script force le statut à `on` via sysfs (`/sys/class/drm/card0-VGA-1/status`) pour réveiller le contrôleur vidéo.
- **Injection de la Modeline exacte :** Il déclare la résolution vidéo exacte via `xrandr` (ex: `1920x1080_60.00` à $148.50\text{ MHz}$ avec $H_{\text{total}}=2200$, $V_{\text{total}}=1125$) et alloue explicitement le contrôleur physique CRTC 0.
- **Désactivation de la distorsion Gamma :** Par défaut, un serveur X11 applique une courbe gamma non linéaire ($\gamma \approx 2.2$) pour la vision humaine. Pour un émetteur RF, cette courbe déformerait l'onde sinusoïdale en harmoniques sévères ! Le script force une **LUT Gamma strictement linéaire de 1.0** (`xrandr --gamma 1.0:1.0:1.0`).
- **Suppression de la mise en veille (DPMS) :** Il désactive les économiseurs d'écran et la gestion d'énergie (`xset -dpms`, `xset s off`) pour empêcher le GPU d'éteindre le RAMDAC en cours de transmission.

---

### 3. Que fait le script Python principal (`vga_sstv.py`) ?

Le script Python orchestre la synthèse et le rendu :
1. **Génération audio SSTV en bande de base (CPU) :**
   - Il charge l'image source et échantillonne chaque ligne de couleur (Vert, Bleu, Rouge) à la cadence Martin 1 standard ($F_s = 48\text{ kHz}$).
   - Il insère le préambule VOX (500 ms à 1900 Hz), l'en-tête numérique VIS (code 44) et les impulsions de synchro ligne (1200 Hz).
   - Il intègre la fréquence instantanée en **double précision `float64` modulo 1.0** pour garantir une continuité de phase absolue sur les 5,5 millions d'échantillons.
2. **Construction des signaux en quadrature ($I/Q$) :**
   - Il calcule les composantes cartésiennes analytiques : $I(t) = \cos(\phi_a(t))$ et $Q(t) = \sin(\phi_a(t))$.
   - Il stocke ces échantillons dans un tableau NumPy bicanal formaté pour la VRAM.
3. **Pilotage de la boucle de trame OpenGL (GLFW / ModernGL) :**
   - Il alloue la fenêtre plein écran avec un verrouillage vertical strict (`swap_interval(1)` et hint de rafraîchissement calé sur la modeline).
   - À chaque trame (toutes les $16.6\text{ ms}$ à 60 Hz), il calcule l'avancement temporel absolu en entier 64-bit (`frame_phase`, `u_audio_frame_base_int` et la fraction résiduelle `u_audio_frame_base_frac`), garantissant **zéro dérive temporelle** sur toute la durée de l'émission.

---

### 4. Que contient la texture VRAM ?

Pour transférer 5,5 millions d'échantillons audio I/Q vers le GPU :
- **Organisation en texture 2D :** OpenGL limite souvent les textures 1D à 8192 ou 16384 éléments. Le signal est donc replié sous la forme d'une texture 2D de **$2048 \times 2700$ pixels**.
- **Format `GL_RG16F` (Float16 bicanal) :**
  - **Canal R (Rouge)** : composante en phase $I(t) = \cos(\phi_{\text{audio}}(t))$.
  - **Canal G (Vert)** : composante en quadrature $Q(t) = \sin(\phi_{\text{audio}}(t))$.
- **Volume mémoire :** L'intégralité des 115 secondes d'émission occupe seulement **21,1 Mo** en VRAM.
- **Interpolation matérielle :** Grâce au filtrage bilinéaire du GPU, le Fragment Shader peut interpoler n'importe quel point temporel sous-échantillon à la volée avec une précision continue sans aliasing.

---

### 5. Que fait le GPU Shader (Fragment Shader GLSL) ?

Le Fragment Shader est exécuté pour **chaque pixel physique scanné par le RAMDAC** (soit **148,5 millions de fois par seconde**) :
1. **Conversion spatio-temporelle :**
   Le shader convertit la position du pixel à l'écran (`gl_FragCoord.xy`, corrigé de haut en bas) en un index temporel d'échantillon au sein de la trame vidéo :
   $$\text{sample\_in\_frame} = (y_{\text{scan}} \times H_{\text{total}}) + x_{\text{scan}}$$
   *Ce calcul intègre naturellement le temps écoulé pendant les porches de synchronisation horizontal ($H_{\text{total}}$).*
2. **Synthèse numérique de la porteuse RF (DDS 32 bits) :**
   La phase de la porteuse à 14.230 MHz avance avec un accumulateur 32-bit entier non signé (modulo $2^{32}$ naturel) :
   $$\theta_c = (\text{u\_frame\_phase} + \text{sample\_in\_frame} \times \text{u\_phase\_inc}) \times \frac{2\pi}{2^{32}}$$
3. **Extraction et interpolation de l'audio I/Q :**
   Le shader calcule l'avancement dans la texture audio, lit les texels voisins et applique une interpolation linéaire :
   $$(I, Q) = \text{mix}(s_0, s_1, \text{frac})$$
4. **Mélangeur en quadrature BLU (Upper Sideband) :**
   La modulation SSB est calculée par le produit cartésien :
   $$\text{RF}(t) = I(t)\cos(\theta_c) - Q(t)\sin(\theta_c) = \cos(\theta_c + \phi_{\text{audio}}(t))$$
5. **Dithering temporel et sortie DAC :**
   - Le signal RF (entre $-1.0$ et $+1.0$) est centré sur la dynamique du DAC : $\text{dac} = 0.5 + 0.5 \times \text{RF}$.
   - Un bruit pseudo-aléatoire variable à chaque trame (`u_frame_phase`) est ajouté pour linéariser le convertisseur 8-bit.
   - La valeur est écrite dans le canal Rouge (`FragColor = vec4(dac, 0.0, 0.0, 1.0)`), connectée directement à la **broche 1 du port VGA**.

---

## 🔬 Les 7 Grands Écueils Techniques et Leurs Solutions

Durant la mise au point de ce projet, nous avons identifié et résolu 7 pièges majeurs invisibles au premier abord :

### 1. La saturation de mantisse `float32` dans la phase audio (Le piège des clics aléatoires)
- **Symptôme** : Au début de la transmission, le son est bon, puis des sauts violents de tonalité et de phase surviennent toutes les quelques secondes.
- **Cause** : À $F_s = 48\text{ kHz}$, une émission de 115 secondes produit $5,5 \times 10^6$ échantillons. Faire `np.cumsum(all_freqs / audio_fs)` en `float32` dépasse $2^{24} \approx 16,7\text{ millions}$ dès quelques secondes de calcul. La précision de mantisse est perdue, créant des erreurs d'arrondi de $2\pi$ radians (bruit de phase massif).
- **Solution** : Accumuler la phase en **double précision 64-bit (`float64`)** et appliquer un modulo $1.0$ strict immédiat avant toute conversion en radians :
  ```python
  cycles = (np.cumsum(all_freqs / audio_fs, dtype=np.float64)) % 1.0
  phase = (2.0 * np.pi * cycles).astype(np.float32)
  ```

---

### 2. Le conflit invisible de rafraîchissement GLFW vs X11 (La vitesse audio doublée)
- **Symptôme** : L'émission SSTV dure 17 secondes au lieu des 115 secondes nominales, les tonalités sont trop aiguës et le signal s'étale sur une fréquence erronée.
- **Cause** : Sur un écran où plusieurs résolutions existent (ex: 1080p @ 60Hz et 1080p @ 120Hz), GLFW en mode plein écran sélectionne automatiquement le taux de rafraîchissement maximal (120 Hz). Si le script Python a mesuré le Pixel Clock à 60 Hz avant d'ouvrir la fenêtre, le GPU tourne en réalité à 285.5 MHz avec un shader calculé pour 148.5 MHz.
- **Solution** :
  1. Forcer le hint GLFW avec le taux de rafraîchissement cible : `glfw.window_hint(glfw.REFRESH_RATE, target_refresh)`.
  2. Ré-interroger `xrandr` immédiatement après l'ouverture de la fenêtre pour confirmer les timings réels sous OpenGL.
  3. Forcer le verrouillage vertical Mesa : `vblank_mode=3` et `__GL_SYNC_TO_VBLANK=1`.

---

### 3. Le hachage FFT par blocs de 1 seconde en réception (Le clic périodique)
- **Symptôme** : L'audio démodulé contient un claquement sec et un décrochage de phase toutes les 1,000000 seconde exactement.
- **Cause** : Découper le flux IQ en tranches de 1 seconde pour appliquer un filtre passe-bande FFT produit des discontinuités de convolution circulaire sur les bords de chaque bloc.
- **Solution** : Traiter l'intégralité du buffer IQ (125 secondes = 30 millions de points à 250 kSps) en **une seule passe FFT globale continue**. L'opération ne prend que 0,7 seconde sur un CPU standard et supprime 100 % des artefacts de bordure.

---

### 4. La gigue de synchronisation ligne par ligne ("Dents de scie")
- **Symptôme** : Les lignes de l'image sont décalées horizontalement les unes par rapport aux autres de $\pm 1$ à $\pm 3$ pixels, rendant les textes flous et les bords crénelés.
- **Cause** : La détection naïve du maximum local de l'impulsion 1200 Hz est sensible au bruit thermique.
- **Solution** :
  1. Remplacer la détection simple par un **filtre adapté cohérent (Matched Filter)** corrélé avec une impulsion complexe de 1200 Hz fenêtrée en Hanning.
  2. Exploiter le fait que les quartz du GPU et du SDR ont une dérive ultra-stable et linéaire.
  3. Utiliser l'estimateur robuste de **Theil-Sen** (médiane des pentes de paires d'impulsions) pour caler une **cadence de ligne unique (PLL logicielle globale)**. L'image résultante a une gigue strictement nulle.

---

### 5. L'en-tête VIS manqué par Robot36 (Image coupée au milieu)
- **Symptôme** : QSSTV ou Robot36 ne détecte pas le début de l'image et commence à décoder à partir du milieu de l'écran.
- **Cause** : Le microphone du smartphone ou la carte son utilise un contrôle automatique de gain (AGC) qui met 100 à 300 ms à réagir. Si la transmission commence directement par le leader VIS de 1900 Hz, le break de 10 ms ou les premiers bits FSK sont saturés ou tronqués.
- **Solution** : Insérer un **préambule VOX/AGC de 500 ms à 1900 Hz** suivi d'un break de 10 ms à 1200 Hz avant l'en-tête VIS officiel. Le récepteur a ainsi le temps d'ouvrir son squelch et de caler son gain audio.

---

### 6. Le voile de petits points réguliers (Dithering spatial vs temporel)
- **Symptôme** : Un léger semis régulier de points colorés apparaît sur les zones sombres.
- **Cause** : 
  - Le dithering statique dans le shader (`gl_FragCoord.xy`) créait une grille géométrique fixe sur l'écran se traduisant par des raies audibles dans le RAMDAC.
  - Le hachage du signal RF par les blankings vidéo VGA (67.5 kHz en horizontal, 60 Hz en vertical).
  - L'écrêtage mono-alternance : en Martin 1, le noir pur est à 1500 Hz. Tout bruit faisant monter la fréquence au-dessus de 1500 Hz devient un point lumineux, tandis que le bruit négatif est tronqué à 0.
- **Solution** : Injecter la phase de trame dans le seed du dithering GLSL pour le rendre **temporellement dynamique** :
  ```glsl
  float seed = dot(gl_FragCoord.xy, vec2(12.9898, 78.233)) + float(u_frame_phase % 10000u) * 0.1337;
  float dither = fract(sin(seed) * 43758.5453) - 0.5;
  dac += dither / 255.0;
  ```
  Le motif spatial fixe est détruit et transformé en un bruit blanc imperceptible.

---

### 7. Le flou des textes dû au redimensionnement
- **Symptôme** : L'indicatif radioamateur est illisible après décodage.
- **Cause** : Créer une mire en haute résolution (ex: 800x640) puis la sous-échantillonner en 320x256 produit des traits de police fins (< 1 pixel). La bande passante vidéo analogique SSTV (~1.1 kHz) lisse ces traits dans le bruit de fond.
- **Solution** : Dessiner la mire directement en **résolution native Martin 1 (320x256)** avec une police ultra-grasse (taille 44) et un halo de contour 1px à contraste maximal (jaune saturé sur noir profond).

---

## 📁 Fichiers et Architecture du Projet

| Fichier | Description |
| :--- | :--- |
| [`vga_sstv.py`](./vga_sstv.py) | **Émetteur radio GPU principal** : Fragment Shader GLSL, synthèse DDS 32-bit, modulation BLU/USB, modes CW, tonalité fixe et Martin 1 avec dithering temporel. |
| [`setup_display.sh`](./setup_display.sh) | Script shell de configuration X11 : force le connecteur VGA, ajoute la modeline 1080p @ 60Hz/120Hz, désactive DPMS et fixe le gamma à 1.0. |
| [`capture_iq.cpp`](./capture_iq.cpp) | Enregistreur streaming C++ haute performance via l'API SoapySDR (compatible SDRplay RSP1, RTL-SDR, HackRF). |
| [`decode_martin1.py`](./decode_martin1.py) | **Décodeur SSTV autonome** : FFT continue, démodulateur FM analytique, filtre adapté 1200 Hz et PLL Theil-Sen zéro-gigue. |
| [`full_sstv_transmission_and_decode.py`](./full_sstv_transmission_and_decode.py) | Orchestrateur complet : synchronise l'enregistrement SDRplay et l'émission GPU, puis produit l'image décodée et les métriques de fidélité. |
| [`generate_test_card.py`](./generate_test_card.py) | Générateur Python de la mire de transmission officielle 320x256 ([`mire_f4jxq.png`](./mire_f4jxq.png)). |
| [`requirements.txt`](./requirements.txt) | Dépendances Python (`moderngl`, `glfw`, `numpy`, `pillow`, `scipy`). |

---

## 📊 Résultats Expérimentaux et Performances

Mesures réalisées en couplage d'air libre (2 brins de 15 cm à 30 cm de distance) sur porteuse **14.230 MHz USB** :

| Métrique | Valeur Obtenue |
| :--- | :--- |
| **Rapport Signal/Bruit RF (SNR)** | **+65.8 dB** sur porteuse CW pure |
| **Rapport Signal/Bruit Audio (PSNR)** | **12.28 dB** sur l'image couleur reconstruite |
| **Erreur Quadratique Moyenne (MSE)** | **3 848** *(sur une échelle de 0 à 65025)* |
| **Corrélation de Pearson (Vert)** | **+0.884** (88.4 % de fidélité au signal théorique) |
| **Corrélation de Pearson (Rouge)** | **+0.866** |
| **Corrélation de Pearson (Bleu)** | **+0.772** |
| **Taux de lignes décodées** | **256 / 256 lignes (100.0 %)** |
| **Reconnaissance automatique** | **100 % validé sous QSSTV et Robot36 Android** |

---

## 73 de F4JXQ ! 📻 Bonnes expérimentations radioamateurs !
