# 📻 Émetteur Radio SSTV & SDR via RAMDAC VGA (GPU DDS)

> **Projet expérimental de radio logicielle (SDR) autonome détournant le convertisseur numérique-analogique (RAMDAC) d'une carte graphique NVIDIA GeForce pour émettre en direct des images SSTV (Martin 1) en bande HF (20m / 14.230 MHz USB).**

*🇬🇧 English version available: [README.en.md](README.en.md) | Interactive animations: [illustrations.en.html](illustrations.en.html)*

Ce guide documente l'ensemble de l'architecture, le protocole expérimental, les principes mathématiques sous-jacents, ainsi que **tous les écueils techniques rencontrés et leurs solutions** pour permettre une reproduction parfaite du banc d'essai.

![Mire SSTV en couleur puis en dégradé de gris, avec le texte "DE F4JXQ SSTV GPU TX GeForce 630". L'ensemble est couvert d'un léger voile de points réguliers](image_recue_v2.png)

Ecoutez le son résultant: [voix française suivi de SSTV suivi de voix anglaise](https://zenodo.org/records/23287769?preview_file=sstv_audio_demod_2152.wav).

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
   - [Étape 4 : Décodage avec QSSTV et Robot36](#étape-4--décodage-avec-qsstv-et-robot36)
6. [Architecture Détaillée de la Solution](#-architecture-détaillée-de-la-solution)
   - [1. Genèse des choix de conception (CPU vs GPU)](#1-pourquoi-cette-architecture--genèse-des-choix-de-conception)
   - [2. Rôle du script de configuration (setup_display.sh)](#2-que-fait-le-script-de-configuration-système-setup_displaysh-)
   - [3. Rôle du moteur Python (vga_sstv.py)](#3-que-fait-le-script-python-principal-vga_sstvpy-)
   - [4. Organisation de la texture VRAM](#4-que-contient-la-texture-vram-)
   - [5. Rôle des Shaders GLSL spécialisés](#5-que-fait-le-gpu-shader-fragment-shader-glsl-)
7. [Les 8 Grands Écueils Techniques et Leurs Solutions](#-les-8-grands-écueils-techniques-et-leurs-solutions)
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
>    La conversion numérique-analogique d'un RAMDAC génère des marches d'escalier et des raies harmoniques vidéo ($f_H$). Si une émission en l'air est effectuée par un radioamateur licencié, un **filtre passe-bas d'ordre 5 ou 7 (type Chebyshev ou Butterworth)** est indispensable pour couper au-delà de 15 MHz.

---

## 🧠 Principe de Fonctionnement

Un écran VGA analogique est piloté par un **RAMDAC** (triple DAC 8-bit rouge/vert/bleu cadencé par un oscillateur quartz matériel, typiquement à **120.00 MHz** ou **148.50 MHz**).

En écrivant un **Fragment Shader OpenGL (GLSL)** exécuté en plein écran par les unités de calcul du GPU, nous calculons pour chaque pixel la valeur instantanée d'une onde radiofréquence :
- Le balayage vidéo horizontal et vertical transforme la succession spatiale des pixels à l'écran en un flux temporel d'échantillons analogiques sur la broche physique **Rouge (Broche 1)** du connecteur VGA.
- La porteuse radio à **14.230 MHz** est synthétisée par **synthèse numérique directe (DDS 32 bits)** dans le shader.
- Le signal audio SSTV (Martin 1) est modulé en **bande latérale supérieure pure (BLU / USB)** via un mélangeur en quadrature cartésien :
  $$\text{RF}(t) = I(t)\cos(\theta_c(t)) - Q(t)\sin(\theta_c(t))$$
  où $I(t)$ et $Q(t)$ sont les composantes analytiques en bande de base de l'audio SSTV pré-calculé, chargées en VRAM dans une texture Float32.

```
[ GPU NVIDIA GT 630 ]
  ├── Cœurs CUDA / Fragment Shader (DDS 32-bit + Mélangeur I/Q USB)
  └── RAMDAC Vidéo (120.00 MSPS ou 148.50 MSPS / 8-bit DAC)
         ├── Broche 1 VGA (Rouge) ────────► Signal RF 14.230 MHz USB
         └── Broche 6 VGA (GND)   ────────► Masse RF
```

---

## 🛠️ Matériel et Câblage Recommandés

### Matériel Testé avec Succès :
- **GPU Émetteur** : NVIDIA GeForce GT 630 (architecture Fermi NVC1 / Kepler GK208) sous Linux avec le pilote open-source `nouveau`.
- **Récepteur SDR** : SDRplay RSP1 (14 bits, 250 kSps) ou clé RTL-SDR v3/v4.
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

# 3. Compilation des outils haute performance C/C++ (Capture SDR & Rendu GPU Déterministe)
make all
# (Génère 'capture_iq' pour SDRplay et 'vga_tx_gpu' pour le scanout GPU)
```

---

## 🚀 Guide Pratique Pas-à-Pas

### Étape 1 : Configuration de la sortie vidéo X11 / Nouveau

Le pilote Nouveau nécessite que la sortie analogique soit physiquement marquée comme active (`connected`) et qu'un CRTC lui soit alloué. Le script [`setup_display.sh`](./setup_display.sh) configure la résolution vidéo et les timings :

```bash
# Si le connecteur est vu comme 'disconnected' par le noyau :
echo on | sudo tee /sys/class/drm/card0-VGA-1/status

# OPTION A (RECOMMANDÉE EN RADIO) : Mode Hors-Bande C (800x2000 @ 60Hz, f_H = 125 kHz)
# Rejette les raies de blanking hors de la bande des 20m (fc + fH = 14.355 MHz > 14.350 MHz) :
DISPLAY=:0 ./setup_display.sh -m 800

# OPTION B : Mode 1080p @ 60Hz standard (1920x1080 @ 60Hz, f_H = 67.5 kHz, 148.50 MHz) :
DISPLAY=:0 ./setup_display.sh -m 60
```
Le script configure la correction gamma à 1.0 (linéarité stricte du DAC) et désactive la mise en veille DPMS.

---

### Étape 2 : Calibration de la porteuse RF (CW)

L'oscillateur quartz de votre carte graphique présente une légère dérive d'usine (généralement entre $+1\text{ ppm}$ et $+5\text{ ppm}$, soit $+20$ à $+65\text{ Hz}$ à $14.230\text{ MHz}$).

1. Ouvrez votre logiciel SDR (**Gqrx**, **SDR#**, ou **CubicSDR**) centré sur **14.230000 MHz** en mode **CW** ou **USB**.
2. Lancez une émission de porteuse pure de calibration :
   ```bash
   DISPLAY=:0 python3 vga_sstv.py --cw -f 14.230e6 --duration 15.0
   ```
3. Relevez la fréquence exacte du pic :
   - En mode 120 MHz (`-m 800`) : **14.230062 MHz** ($+62\text{ Hz}$).
   - En mode 148.5 MHz (`-m 60`) : **14.230034 MHz** ($+34\text{ Hz}$).
   Cette valeur précise est réutilisée par le récepteur pour caler exactement le mélangeur numérique en bande de base.

---

### Étape 3 : Émission et Décodage SSTV Automatisé

1. Générez la mire d'essai officielle haute visibilité :
   ```bash
   # Utilisation par défaut (F4JXQ sur 14.230 MHz USB, sortie mire_f4jxq.png) :
   python3 generate_test_card.py

   # Ou personnalisée avec votre propre indicatif :
   python3 generate_test_card.py F4JXQ -f 14.230 -m USB
   ```

2. Exécutez le script d'orchestration end-to-end :
   ```bash
   # En mode Hors-Bande C (800x2000 @ 120 MHz) avec moteur C/C++ haute cadence :
   python3 full_sstv_transmission_and_decode.py -c 14230062 --cpp

   # En mode standard 1080p (148.5 MHz) :
   python3 full_sstv_transmission_and_decode.py -c 14230034 --cpp
   ```
   Ce script :
   - Démarre la capture SDRplay en arrière-plan à 250 kSps sur $14.220\text{ MHz}$.
   - Lance la transmission SSTV GPU sur la machine émettrice via SSH (en déléguant au moteur C ultra-déterministe `vga_tx_gpu` si `--cpp` est spécifié).
   - À la fin des 125 secondes, démodule le flux en bande de base USB, extrait l'audio dans [`sstv_audio_demod.wav`](./sstv_audio_demod.wav), décode les 256 lignes et génère l'image finale [`image_recue.png`](./image_recue.png).

---

### Étape 4 : Décodage avec QSSTV et Robot36

Le signal audio produit est 100 % conforme aux standards radioamateurs internationaux :

- **Avec QSSTV (Linux PC)** :
  1. Lancez `qsstv`.
  2. Configurez l'entrée audio sur votre récepteur SDR (via PulseAudio/PipeWire) ou allez dans **File ➔ Play audio file** et sélectionnez [`sstv_audio_demod.wav`](./sstv_audio_demod.wav).
  3. QSSTV détecte automatiquement le mode Martin 1, synchronise l'en-tête VIS et affiche l'image reçue en couleur sans aucune ligne coupée ni inclinaison.
- **Avec Robot36 (Smartphone Android)** :
  1. Ouvrez l'application **Robot36** sur votre smartphone.
  2. Lancez la transmission ou jouez le fichier audio démodulé (`paplay sstv_audio_demod.wav`).
  3. L'application se synchronise automatiquement grâce au préambule VOX et dessine la mire ligne par ligne.

---

## 🏛️ Architecture Détaillée de la Solution

Pour transformer une simple carte graphique grand public en émetteur radio BLU (USB) capable de transmettre 115 secondes d'image couleur SSTV à 120 ou 150 millions d'échantillons par seconde, une architecture hybride **CPU (Pré-calcul haute fidélité) + GPU (Synthèse et mélange temps réel)** a été conçue.

### 1. Pourquoi cette architecture ? (Genèse des choix de conception)

Lorsqu'on cherche à générer un signal radio à $14.230\text{ MHz}$ :
1. **L'impossibilité du CPU seul :** Un processeur généraliste sous Linux ne peut pas débiter un flux d'échantillons analogiques continu à 150 MSPS sans gigue. L'ordonnanceur de l'OS (changements de contexte, gestion des interruptions, cache misses) introduit des micro-coupures de quelques microsecondes qui détruiraient irrémédiablement la phase de l'onde radio.
2. **La puissance du RAMDAC matériel :** La carte graphique possède son propre convertisseur numérique-analogique (RAMDAC), cadencé par un oscillateur quartz matériel indépendant ($120.00\text{ MHz}$ ou $148.50\text{ MHz}$). Une fois le flux d'affichage lancé, le RAMDAC lit la mémoire vidéo et génère le signal analogique de manière strictement ininterrompue, insensible à la charge CPU de l'OS.
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
                   Transfert VRAM (Texture 2D RG32F)
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                           GPU (FRAGMENT SHADER GLSL)                        |
|  1. gl_FragCoord.xy  ──►  sample_in_frame (intègre porches H_total/V_total)  |
|  2. DDS 32-bit       ──►  Porteuse RF pure : θ_c = frame_phase + n*Δθ       |
|  3. Texel Fetch      ──►  Indexation bit-à-bit (& 2047u, >> 11)             |
|  4. Mix linéaire     ──►  Interpolation continue I(t) et Q(t)               |
|  5. Mélangeur USB    ──►  RF(t) = I(t)*cos(θ_c) - Q(t)*sin(θ_c)             |
|  6. Dither temporel  ──►  DAC = 0.5 + 0.5*RF + dither(u_frame_phase)        |
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
- **Injection de la Modeline exacte :** Il déclare la résolution vidéo exacte via `xrandr` (ex: `800x2000_125k` à $120.00\text{ MHz}$ ou `1920x1080_60.00` à $148.50\text{ MHz}$) et alloue explicitement le contrôleur physique CRTC 0.
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
   - Il stocke ces échantillons dans un tableau NumPy bicanal formaté pour la VRAM en Float32 (`f4`).
3. **Pilotage de la boucle de trame OpenGL (GLFW / ModernGL) :**
   - Il alloue la fenêtre avec verrouillage vertical strict (`swap_interval(1)`).
   - Il désactive le ramasse-miettes (`gc.disable()`) et déporte l'affichage console dans un thread indépendant pour garantir qu'aucune pause Python n'interrompe la cadence de trame.
   - À chaque trame, il calcule l'avancement temporel absolu en entier 64-bit (`frame_phase`, `u_audio_frame_base_int` et la fraction résiduelle `u_audio_frame_base_frac`), garantissant **zéro dérive temporelle** sur toute la durée de l'émission.
4. **Export de textures et intégration du moteur C/C++ (`vga_tx_gpu`) :**
   - Possibilité d'exporter la texture pré-calculée dans un fichier conteneur binaire `.sstvtex` (`--save-texture`).
   - Possibilité de déléguer l'émission en temps réel au binaire C/C++ dédié (`--cpp`) pour garantir un scanout sans aucune gigue d'interpréteur ou de GC.

---

### 3b. Rôle du moteur de rendu C/C++ haute cadence (`vga_tx_gpu`)

Pour éliminer totalement le surcoût de l'interpréteur Python, du GIL et des potentielles pauses du runtime lors des cadences de trame rapides (> 100 Hz) :
- **Exécution pure C (OpenGL 3.3 Core Profile + X11)** : latence de rendu par trame < 5 microsecondes.
- **Support des priorités temps réel Linux (`SCHED_FIFO`)** via `--realtime` / `-r`.
- **Compatibilité complète** : accepte les textures binaires `.sstvtex` ou génère les porteuses CW et tonalités pures directement.

---

### 4. Que contient la texture VRAM ?

Pour transférer 5,5 millions d'échantillons audio I/Q vers le GPU :
- **Organisation en texture 2D :** Le signal est replié sous la forme d'une texture 2D de **$2048 \times 2712$ pixels**.
- **Format `GL_RG32F` (Float32 bicanal) :**
  - **Canal R (Rouge)** : composante en phase $I(t) = \cos(\phi_{\text{audio}}(t))$.
  - **Canal G (Vert)** : composante en quadrature $Q(t) = \sin(\phi_{\text{audio}}(t))$.
- **Volume mémoire :** L'intégralité des 115 secondes d'émission occupe **42,4 Mo** en VRAM, avec une dynamique de 24 bits de mantisse (bruit de fond à $-140\text{ dB}$).

---

### 5. Que font les GPU Shaders (Fragment Shaders GLSL) ?

Trois shaders spécialisés (`FRAGMENT_SHADER_CW`, `FRAGMENT_SHADER_TONE`, `FRAGMENT_SHADER_SSTV`) éliminent tout branchement dynamique d'exécution au niveau fragment :
1. **Conversion spatio-temporelle :**
   Le shader convertit la position du pixel à l'écran (`gl_FragCoord.xy`) en un index temporel d'échantillon au sein de la trame vidéo :
   $$\text{sample\_in\_frame} = (y_{\text{scan}} \times H_{\text{total}}) + x_{\text{scan}}$$
2. **Synthèse numérique de la porteuse RF (DDS 32 bits) :**
   La phase de la porteuse avance avec un accumulateur 32-bit entier non signé (modulo $2^{32}$ naturel) :
   $$\theta_c = (\text{u\_frame\_phase} + \text{sample\_in\_frame} \times \text{u\_phase\_inc}) \times \frac{2\pi}{2^{32}}$$
3. **Extraction et interpolation continue de l'audio I/Q :**
   Le shader calcule l'adresse dans la texture avec des masques bit-à-bit ultra-rapides (`& 2047u`, `>> 11`), lit les texels voisins $s_0$ et $s_1$ via `texelFetch`, puis applique une interpolation linéaire `mix(s0, s1, frac)`.
4. **Mélangeur en quadrature BLU (Upper Sideband) :**
   La modulation SSB est calculée par le produit cartésien :
   $$\text{RF}(t) = I(t)\cos(\theta_c) - Q(t)\sin(\theta_c) = \cos(\theta_c + \phi_{\text{audio}}(t))$$
5. **Dithering temporel et sortie DAC :**
   - Le signal RF est centré sur la dynamique du DAC : $\text{dac} = 0.5 + 0.5 \times \text{RF}$.
   - Un bruit pseudo-aléatoire variable à chaque trame (`u_frame_phase`) est ajouté pour linéariser le convertisseur 8-bit.
   - La valeur est écrite dans le canal Rouge (`FragColor = vec4(dac, 0.0, 0.0, 1.0)`), connectée directement à la **broche 1 du port VGA**.

---

## 🔬 Les 8 Grands Écueils Techniques et Leurs Solutions

### 1. La saturation de mantisse `float32` dans la phase audio
- **Symptôme** : Sauts violents de tonalité et de phase après quelques secondes d'émission.
- **Cause** : À $48\text{ kHz}$, `np.cumsum(all_freqs / audio_fs)` en `float32` dépasse $2^{24}$ en quelques secondes, perdant la précision de mantisse et provoquant des erreurs d'arrondi de phase.
- **Solution** : Accumuler la phase en **double précision 64-bit (`float64`)** avec un modulo $1.0$ strict avant toute conversion en radians.

---

### 2. Le conflit de détection de géométrie GLFW vs X11
- **Symptôme** : Audio déformé, vitesse anormale ou fenêtre refusant de s'ouvrir.
- **Cause** : Si la résolution active n'est pas 1080p (ex: 800x2000), créer une fenêtre hardcodée en 1920x1080 provoque des artefacts de mise à l'échelle Mesa et un décalage d'échantillonnage.
- **Solution** : Implémentation de `detect_active_display_timings()` interrogeant dynamiquement `xrandr` pour extraire automatiquement largeur, hauteur, Pixel Clock, $H_{\text{total}}$ et $V_{\text{total}}$ réels.

---

### 3. Le hachage FFT par blocs de 1 seconde en réception
- **Symptôme** : Clics périodiques et décrochages de phase toutes les 1,000000 seconde dans l'audio démodulé.
- **Cause** : Le découpage par blocs produit des discontinuités de convolution circulaire sur les bords.
- **Solution** : Filtrage passe-bande en **une seule passe FFT globale continue** sur l'intégralité du buffer IQ (125 secondes).

---

### 4. La détection de synchro ligne et centrage horizontal
- **Symptôme** : Lignes décalées horizontalement en dents de scie ou image tronquée avec bordure blanche enroulée à gauche.
- **Cause** : Détection naïve de crête sensible au bruit thermique, et fenêtre de recherche de centrage horizontal trop étroite.
- **Solution** :
  1. Filtre adapté cohérent (Matched Filter 1200 Hz).
  2. Saut direct sur l'impulsion de la Ligne 0 après le bit stop VIS (évite d'accrocher sur le bit stop de 30 ms).
  3. Régression linéaire robuste (`np.polyfit`) sur l'ensemble des impulsions détectées pour verrouiller une pente unique.
  4. Fenêtre d'optimisation de centrage élargie à $[-1500, +1500]$ échantillons, calant la première barre blanche exactement à $x = 0$.

---

### 5. L'en-tête VIS manqué par Robot36 / QSSTV
- **Symptôme** : QSSTV ou Robot36 démarre au milieu de l'écran ou rate la synchronisation.
- **Cause** : L'AGC du récepteur met 100 à 300 ms à réagir.
- **Solution** : Insérer un **préambule VOX/AGC de 500 ms à 1900 Hz** suivi d'un break de 10 ms à 1200 Hz avant l'en-tête VIS.

---

### 6. Le voile de petits points réguliers (Dithering spatial vs temporel)
- **Symptôme** : Grille géométrique fixe ou petits points réguliers sur les zones sombres.
- **Cause** : Dithering spatial statique dépendant uniquement de `gl_FragCoord.xy`.
- **Solution** : Injecter la phase de trame dans le seed du dithering GLSL pour le rendre **temporellement dynamique**.

---

### 7. Le flou des textes dû au redimensionnement
- **Symptôme** : Indicatif illisible après décodage.
- **Cause** : Sous-échantillonnage d'une image haute résolution lissant les traits fins.
- **Solution** : Dessin de la mire directement en **résolution native Martin 1 (320x256)** avec police grasse et halo de contraste maximal.

---

### 8. Le dilemme des harmoniques hors-bande vs rafraîchissement vertical (La solution $800\times 2000$)
- **Symptôme** :
  - En mode $800\times 600$ @ 201 Hz : Le GPU manquait $0{,}5\%$ des vsyncs, provoquant une dérive cumulative de $5100\text{ PPM}$ et une **pente oblique très marquée**.
  - En mode $800\times 600$ étendu à 60 Hz avec $V_{\text{total}}=2083$ : Le blanking vertical de 71 % hachait la porteuse à 60 Hz, créant des rayures horizontales noires.
- **Cause** : Pour avoir $f_H = 125\text{ kHz}$ (harmoniques hors bande 20m), $V_{\text{total}}$ doit être égal à $f_H / f_V = 125000 / 60 = 2083$. Si la hauteur active n'est que de 600 lignes, le RAMDAC est éteint 71 % du temps !
- **Solution** : Définir une résolution active de **2000 lignes** ($800\times 2000$ @ 60 Hz) :
  - $f_H = 125{,}000\text{ kHz}$ est conservé ($PCLK = 120{,}00\text{ MHz}$, $H_{\text{total}} = 960$).
  - $f_V = 60{,}01\text{ Hz}$ ($16{,}66\text{ ms}$/trame) offre une marge énorme au GPU -> **0 trame en retard (0,0 %)**, zéro pente.
  - Le rapport cyclique utile atteint **$96{,}0\%$** (blanking réduit à $4{,}0\%$, rayures de hachage éliminées).
  - La première harmonique supérieure est à **$14{,}355\text{ MHz}$**, strictement au-dessus de la limite des 20 m ($14{,}350\text{ MHz}$).

---

## 📁 Fichiers et Organisation du Projet


Un enregistrement SigMF est disponible sur Zenodo : [SSB and SSTV GPU Generated - SDRPlay RSP1 Capture - 14M220 - 2026-10-10 21:52 CET](https://doi.org/10.5281/zenodo.23287769). Vous y trouverez aussi 2 images décodées une par QSSTV, un par le script python.


| Fichier | Description |
| :--- | :--- |
| [`vga_sstv.py`](./vga_sstv.py) | **Émetteur radio GPU principal** : Shaders GLSL optimisés (CW, TONE, SSTV), synthèse DDS 32 bits, modulation BLU/USB, texture Float32, détection automatique des timings vidéo et boucle temps réel sans gigue. |
| [`setup_display.sh`](./setup_display.sh) | Script shell de configuration CRTC : force le port VGA, applique les modelines ($800\times 2000$ Hors-Bande, $1024\times 2000$, ou 1080p), désactive DPMS et fixe le gamma à 1.0. |
| [`capture_iq.cpp`](./capture_iq.cpp) | Enregistreur streaming C++ haute performance via SoapySDR cadencé à 250 kSps (élimine les overflows SDRplay). |
| [`decode_martin1.py`](./decode_martin1.py) | **Décodeur SSTV autonome** : FFT globale continue, démodulateur FM analytique, filtre adapté 1200 Hz, régression linéaire PLL et centrage horizontal $[-1500, +1500]$. |
| [`full_sstv_transmission_and_decode.py`](./full_sstv_transmission_and_decode.py) | Orchestrateur complet : synchronise l'enregistrement SDRplay et l'émission GPU via SSH, puis produit l'image décodée et les métriques de fidélité. |
| [`generate_test_card.py`](./generate_test_card.py) | Générateur Python de la mire de transmission officielle 320x256 ([`mire_f4jxq.png`](./mire_f4jxq.png)). |
| [`illustrations.html`](./illustrations.html) | Démonstrateur interactif HTML5 autonome avec 5 animations et simulateurs Canvas temps réel. |
| [`illustrations.en.html`](./illustrations.en.html) | Version anglaise du démonstrateur interactif HTML5 (`illustrations.html`). |
| [`README.en.md`](./README.en.md) | Version anglaise complète de la présente documentation. |
| [`CURRENT_STATE.md`](./CURRENT_STATE.md) | Synthèse technique détaillée, journal des essais et matrice comparative des modes d'émission. |
| [`requirements.txt`](./requirements.txt) | Dépendances Python (`moderngl`, `glfw`, `numpy`, `pillow`, `scipy`). |

---

## 📊 Résultats Expérimentaux et Performances

Mesures réalisées en transmission complète de 125 secondes en couplage d'air libre sur porteuse **14.230 MHz USB** :

| Métrique | Mode 1080p @ 60 Hz Standard | Mode $800\times 2000$ @ 60 Hz Hors-Bande (Recommandé) |
| :--- | :---: | :---: |
| **Pixel Clock ($PCLK$)** | 148.50 MHz | **120.00 MHz** |
| **Fréquence ligne $f_H$** | 67.50 kHz | **125.000 kHz** |
| **Harmonique supérieure ($f_c + f_H$)** | 14.2975 MHz *(Dans bande 20m)* | **14.355 MHz *(Strictement hors bande 20m)*** |
| **Harmonique inférieure ($f_c - f_H$)** | 14.1625 MHz *(Dans bande 20m)* | **14.105 MHz *(CW/digimodes)*** |
| **Pollution sous-bande phonie SSB** | Présente ($\pm 67.5$ kHz) | **Éliminée (Aucune raie dans 14.150–14.350 MHz)** |
| **Trames en retard GPU** | 0 (0.0 %) | **0 (0.0 %)** |
| **Pente de l'image SSTV** | **Nulle (Pente = 0)** | **Nulle (Pente = 0)** |
| **Rapport Signal/Bruit (PSNR)** | **19.56 dB** | **16.62 dB** |
| **Erreur Quadratique Moyenne (MSE)** | **720.1** | **1416.2** *(sur 65025)* |
| **Corrélation de Pearson (Vert)** | **+0.977** (97.7 %) | **+0.959** (95.9 %) |
| **Corrélation de Pearson (Rouge)** | **+0.977** (97.7 %) | **+0.955** (95.5 %) |
| **Corrélation de Pearson (Bleu)** | **+0.972** (97.2 %) | **+0.913** (91.3 %) |
| **Taux de lignes décodées** | **256 / 256 lignes (100.0 %)** | **256 / 256 lignes (100.0 %)** |
| **Reconnaissance automatique** | **100 % sous QSSTV et Robot36** | **100 % sous QSSTV et Robot36** |

---

## 73 de F4JXQ ! 📻 Bonnes expérimentations radioamateurs !

> ℹ️ **Transparence Éditoriale (Conformité EU AI Act) :** Cet article a été généré par un assistant IA sous la direction éditoriale et la structuration d'un auteur humain, qui en assure la relecture, la vérification technique, et la responsabilité du contenu (relecture en cours).
