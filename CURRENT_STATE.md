# État des Lieux et Compte-Rendu Technique : Émetteur SSTV Martin 1 via GPU RAMDAC

**Date :** 9 octobre 2026 (08h50)  
**Auteur :** Loïc Fejoz / Assistant Antigravity  
**Projet :** `vga-hamradio` (PoC Émission Radioamateur via détournement de RAMDAC VGA)

---

## 1. Synthèse des Résultats Obtenus

### 1.1. Validation du Mode « Harmoniques Hors-Bande 20m » ($800\times 2000$ @ 60 Hz)
Une transmission complète de 125 secondes de la mire [mire_f4jxq.png](file:///home/loic/projets/vga-hamradio/mire_f4jxq.png) (320×256) a été réalisée avec succès en mode vidéo custom haute réjection spectrale et décodée numériquement via [full_sstv_transmission_and_decode.py](file:///home/loic/projets/vga-hamradio/full_sstv_transmission_and_decode.py).

* **Fréquence ligne horizontale ($f_H$) :** **$125{,}000\text{ kHz}$** ($PCLK = 120{,}00\text{ MHz}$, $H_{\text{total}} = 960$).
* **Harmoniques de blanking dans l'éther :**
  * $f_c + f_H = 14{,}230062 + 0{,}125000 = \mathbf{14{,}355062\text{ MHz}}$ (**strictement au-dessus de la limite haute de la bande 20m** $14{,}350\text{ MHz}$).
  * $f_c - f_H = 14{,}105062\text{ MHz}$ (rejeté loin de la sous-bande phonie/SSTV, dans la portion CW/digimodes).
  * $f_c \pm 2f_H = 14{,}480\text{ MHz}$ et $13{,}980\text{ MHz}$ (toutes deux hors bande 20m).
  * **Zéro raie parasite de blanking dans toute la sous-bande SSB phonie ($14{,}150 - 14{,}350\text{ MHz}$) !**
* **Lignes décodées :** **256 / 256 lignes complètes (100.0 %)**.
* **Cadence de balayage mesurée :** **21429.2694 échantillons/ligne** à $F_s = 48\text{ kHz}$.
* **Dérive mesurée :** **-0.14 échantillon/ligne** (-6.5 PPM par rapport à la cadence Martin 1 théorique de 21429.408 éch/ligne).
* **Alignement vertical (pente) :** **Pente = 0** (alignement strictement vertical sur toute la hauteur de l'image).
* **Fidélité globale (image complète 256 lignes) :**
  * **PSNR : 16.62 dB**
  * Erreur Quadratique Moyenne : **1416.2** (sur 65025)
  * Corrélation canal Rouge : **+0.955** (95.5 %)
  * Corrélation canal Vert : **+0.959** (95.9 %)
  * Corrélation canal Bleu : **+0.913** (91.3 %)
* **Comportement temps réel :**
  * Trames en retard sur le GPU : **0 (0.0 %)**.
  * Aucune 2ème image initiée sous QSSTV.

---

## 2. Analyse Technique & Résolution du Défi « Harmoniques Hors-Bande »

### 2.1. Pourquoi le mode initial $800\times 600$ @ 201 Hz échouait
* En configuration standard VESA pour atteindre $f_H = 125\text{ kHz}$ avec une résolution de 600 lignes ($V_{\text{total}} = 620$), la fréquence de rafraîchissement vertical s'élevait à **$201{,}61\text{ Hz}$**.
* À $201\text{ Hz}$, l'intervalle entre trames physiques est de seulement $4{,}96\text{ ms}$. Même sans Garbage Collector (`gc.disable()`), l'ordonnancement X11/Mesa accumulait un retard sur environ $0{,}5\%$ des buffers swaps (36 trames en retard sur 35 secondes).
* Chaque trame manquée gelait l'émission physique de $4{,}96\text{ ms}$, introduisant une dilatation temporelle cumulative de **$5100\text{ PPM}$** et une **pente oblique catastrophique** (~5 pixels de décalage par ligne SSTV).

### 2.2. Pourquoi le mode $800\times 600$ avec grand blanking vertical échouait
* En augmentant $V_{\text{total}}$ à 2083 pour forcer $f_V = 60\text{ Hz}$ tout en gardant $V_{\text{active}} = 600$, le blanking vertical représentait 1483 lignes sur 2083 (**71 % du temps**).
* Le RAMDAC s'éteignait (0.0 V) pendant 11.8 ms toutes les 16.6 ms, créant une modulation d'amplitude en créneau à 60 Hz et des rayures horizontales noires traversant l'image reçue.

### 2.3. La percée : Le Modeline Custom $800 \times 2000$ @ 60 Hz
En augmentant la hauteur active $V_{\text{active}}$ à 2000 lignes pour $V_{\text{total}} = 2083$ :
1. **$f_H = 125{,}000\text{ kHz}$** est conservé ($PCLK = 120{,}00\text{ MHz}$, $H_{\text{total}} = 960$).
2. **$f_V = 60{,}01\text{ Hz}$** ($T_{\text{frame}} = 16{,}66\text{ ms}$) garantit une marge temporelle énorme pour le GPU -> **0 trame en retard (0.0 %)**.
3. **Rapport cyclique RF de $96{,}0\%$ utile** (blanking réduit à $4{,}0\%$, rayures 60 Hz éliminées).
4. **Charge de remplissage GPU minime :** $800 \times 2000 \times 60 = 96\text{ MPix/s}$ (très largement sous la limite de la GeForce GT 630).

---

## 3. Matrice Comparative des Modes Vidéo Émetteurs

| Paramètre | Mode 1080p @ 60 Hz Standard (Labo) | Mode $800\times 600$ @ 201 Hz (Rejeté) | Mode $800\times 2000$ @ 60 Hz (Validé Hors-Bande) |
| :--- | :---: | :---: | :---: |
| **Pixel Clock ($PCLK$)** | 148.50 MHz | 120.00 MHz | **120.00 MHz** |
| **Fréquence ligne $f_H$** | 67.50 kHz | 125.00 kHz | **125.000 kHz** |
| **Harmonique sup. $f_c + f_H$** | 14.2975 MHz *(Dans bande 20m)* | 14.355 MHz *(Hors bande 20m)* | **14.355 MHz *(Hors bande 20m)*** |
| **Harmonique inf. $f_c - f_H$** | 14.1625 MHz *(Dans bande 20m)* | 14.105 MHz *(CW)* | **14.105 MHz *(CW)*** |
| **Pollution bande SSB 20m** | **OUI** (raies à $\pm 67.5$ kHz) | NON | **NON (Éliminée)** |
| **Fréquence rafraîchissement $f_V$** | 60.00 Hz | 201.61 Hz | **60.01 Hz** |
| **Rapport cyclique RF** | 96.0 % | 96.8 % | **96.0 %** |
| **Trames en retard GPU** | 0 (0.0 %) | 36 / 35s (0.5 %) | **0 (0.0 %)** |
| **Pente de l'image SSTV** | Nulle (0) | Forte diagonale | **Nulle (0)** |
| **Fidélité globale (PSNR)** | **19.56 dB** | < 5 dB | **16.62 dB** |
| **Corrélation RVB** | **97.7% / 97.7% / 97.2%** | < 25% | **95.5% / 95.9% / 91.3%** |

---

## 4. Répartition des Composants & Architecture Logicielle

* **Poste Émetteur TX (`my-yuno` / `192.168.1.26`) :**
  - Carte graphique : NVIDIA GeForce GT 630 (pilote `nouveau`).
  - [setup_display.sh](file:///home/loic/projets/vga-hamradio/setup_display.sh) : Configure la sortie `VGA-1`, applique la modeline ($800\times 2000$ ou 1080p), gamma à 1.0, DPMS off.
  - [vga_sstv.py](file:///home/loic/projets/vga-hamradio/vga_sstv.py) : Moteur d'émission temps réel ModernGL/GLFW avec shaders dédiés (`CW`, `TONE`, `SSTV`), texture I/Q Float32 (`GL_RG32F`), auto-détection dynamique de résolution via `xrandr`, `gc.disable()` et dithering temporel.
  - *(Note : aucun décodeur n'est requis sur le Tx)*.

* **Poste Récepteur RX (Machine locale `fixe-loic`) :**
  - Matériel SDR : SDRplay RSP1 connecté en USB.
  - [capture_iq.cpp](file:///home/loic/projets/vga-hamradio/capture_iq.cpp) : Capture streaming binaire CF32 à 250 kSps via SoapySDR.
  - [decode_martin1.py](file:///home/loic/projets/vga-hamradio/decode_martin1.py) : Décodeur autonome (translation IF USB, FFT continue globale, discriminateur FM, matched filter 1200 Hz, PLL linéaire robuste et calage horizontal $[-1500, +1500]$).
  - [full_sstv_transmission_and_decode.py](file:///home/loic/projets/vga-hamradio/full_sstv_transmission_and_decode.py) : Orchestrateur synchronisant la capture SDR locale et l'émission distante via SSH.

---

## 5. Commandes de Référence pour les Tests

```bash
# 1. Configurer le mode hors-bande sur l'émetteur :
ssh loic@192.168.1.26 "DISPLAY=:0 ~/projets/vga-hamradio/setup_display.sh -m 800"

# 2. Calibration porteuse pure (CW 15 secondes) :
ssh loic@192.168.1.26 "cd ~/projets/vga-hamradio && DISPLAY=:0 .venv/bin/python3 vga_sstv.py --cw -f 14.230e6 --duration 15"

# 3. Émission complète et décodage automatique (Mode Hors-Bande fc = 14.230062 MHz) :
python3 full_sstv_transmission_and_decode.py -c 14230062 --cpp

# 4. Émission complète et décodage automatique (Mode Labo 1080p fc = 14.230034 MHz) :
python3 full_sstv_transmission_and_decode.py -c 14230034
```
