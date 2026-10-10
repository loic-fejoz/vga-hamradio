# 📡 Rapport d'Analyse Spectrale & Guide de Filtrage RF : Émetteur VGA-SDR

> **Projet :** Émission Radio SSTV (Martin 1) / SDR via GPU RAMDAC (DDS GLSL)  
> **Auteur :** F4JXQ / Laboratoire d'expérimentation GPU SDR  
> **Cible RF :** Bande des 20 mètres (14.230 MHz USB)  
> **Fichier de référence :** `FILTER.md`

---

## 📑 Sommaire

1. [Contexte et Architecture du Système](#1-contexte-et-architecture-du-système)
2. [Diagnostic Spectral des Deux Hypothèses d'Émission](#2-diagnostic-spectral-des-deux-hypothèses-démission)
   - [Hypothèse 1 : Mode Laboratoire 1080p @ 60 Hz (f_H = 67.5 kHz)](#hypothèse-1--mode-laboratoire-1080p--60-hz-f_h--675-khz)
   - [Hypothèse 2 : Mode Hors-Bande 800x2000 @ 60 Hz (f_H = 125.0 kHz)](#hypothèse-2--mode-hors-bande-800x2000--60-hz-f_h--1250-khz)
   - [Origine physique du découpage par le blanking](#origine-physique-du-découpage-par-le-blanking)
   - [Démonstration mathématique de la modulation de blanking](#démonstration-mathématique-de-la-modulation-de-blanking)
3. [Contraintes Réglementaires (ANFR / ITU-R) selon l'Hypothèse](#3-contraintes-réglementaires-anfr--itu-r-selon-lhypothèse)
   - [Rappel des exigences sur les rayonnements non essentiels](#rappel-des-exigences-sur-les-rayonnements-non-essentiels)
   - [Impact sur le plan de bande des 20 mètres](#impact-sur-le-plan-de-bande-des-20-mètres)
4. [Recommandations de Filtrage Adaptées aux Deux Hypothèses](#4-recommandations-de-filtrage-adaptées-aux-deux-hypothèses)
   - [Schéma synoptique de la chaîne d'émission](#schéma-synoptique-de-la-chaîne-démission)
   - [Étage commun : Découplage DC et adaptation d'impédance 75 Ω ➔ 50 Ω](#étage-commun--découplage-dc-et-adaptation-dimpédance-75-ω--50-ω)
   - [Branche A (Pour Hypothèse 1 : 1080p @ 60 Hz) : Filtrage ultra-sélectif à quartz](#branche-a-pour-hypothèse-1--1080p--60-hz--filtrage-ultra-sélectif-à-quartz)
   - [Branche B (Pour Hypothèse 2 : Mode Hors-Bande 125 kHz) : Filtrage LC standard ou Cauer](#branche-b-pour-hypothèse-2--mode-hors-bande-125-khz--filtrage-lc-standard-ou-cauer)
   - [Matrice comparative des deux solutions de filtrage](#matrice-comparative-des-deux-solutions-de-filtrage)
   - [Étages d'amplification linéaire (Classe A / AB QRP)](#étages-damplification-linéaire-classe-a--ab-qrp)
5. [Protocole de Validation et Mesures Avant Émission sur Antenne](#5-protocole-de-validation-et-mesures-avant-émission-sur-antenne)

---

## 1. Contexte et Architecture du Système

Le projet `vga-hamradio` détourne le triple convertisseur numérique-analogique (**RAMDAC 8-bit**) d'une carte graphique NVIDIA pour générer directement un signal radiofréquence modulé en **Bande Latérale Supérieure (BLU / USB)** à $14.230\text{ MHz}$ :

1. **Horloge matérielle :** Le RAMDAC est cadencé par un quartz vidéo autonome ($f_{\text{pixel}} = 120.00\text{ MHz}$ ou $148.50\text{ MHz}$).
2. **Génération DDS & Modulation :** Un fragment shader OpenGL calcule pour chaque pixel la phase d'une onde porteuse et la multiplie par les composantes en quadrature $I(t)$ et $Q(t)$ de l'audio SSTV pré-calculé :
   $$\text{RF}(t) = I(t)\cos(\theta_c(t)) - Q(t)\sin(\theta_c(t))$$
3. **Sortie Physique :** Le signal analogique $0.0\text{ V} - 0.7\text{ V}$ est extrait entre la **Broche 1** (Canal Rouge) et la **Broche 6** (Masse RF) de la prise DE-15 (VGA).

Bien que cette technique fournisse un signal d'un excellent rapport signal/bruit local ($> 65\text{ dB}$ mesuré en champ proche), l'architecture de balayage vidéo analogique introduit intrinsèquement des bandes latérales de découpage qui imposent des stratégies de filtrage distinctes selon le mode d'affichage retenu.

---

## 2. Diagnostic Spectral des Deux Hypothèses d'Émission

L'émetteur peut fonctionner selon **deux hypothèses d'affichage** présentant chacune un profil spectral et des contraintes de filtrage radicalement différents.

### Hypothèse 1 : Mode Laboratoire 1080p @ 60 Hz ($f_H = 67.5\text{ kHz}$)

* **Timings vidéo :** $1920\times 1080$, $H_{\text{total}} = 2200$, $V_{\text{total}} = 1125$, $PCLK = 148.50\text{ MHz}$.
* **Fréquence ligne :** $f_H = 148.50\text{ MHz} / 2200 = \mathbf{67.500\text{ kHz}}$.
* **Avantage :** Sur-échantillonnage élevé ($10.4$ éch/période RF), très faible temps de blanking ($12.7\%$), fidélité maximale en réception locale (PSNR de **$19.56\text{ dB}$**, corrélation $> 97.7\%$).
* **Inconvénient spectral majeur :** Les raies de blanking tombent directement dans la bande radioamateur des 20 mètres.

| Composante Fréquentielle | Fréquence Mesurée | Écart vs Porteuse | Niveau Relatif (dBc) | Classification Bande 20m |
| :--- | :--- | :--- | :--- | :--- |
| **Porteuse SSTV utile** | **14.230034 MHz** | $0\text{ kHz}$ | **0.0 dBc** (Référence) | **Signal désiré (SSTV)** |
| **Raie de blanking basse ($-f_H$)** | **14.1625 MHz** | **$-67.50\text{ kHz}$** | **-38.7 dBc** | ⚠️ **Sous-bande Phonie SSB DX (Brouillage)** |
| **Raie de blanking haute ($+f_H$)** | **14.2975 MHz** | **$+67.50\text{ kHz}$** | **-37.8 dBc** | ⚠️ **Sous-bande Phonie SSB haute (Brouillage)** |
| **Harmonique blanking 2 ($-2f_H$)** | **14.0950 MHz** | **$-135.00\text{ kHz}$** | **-48.9 dBc** | Sous-bande Numérique / CW |
| **Harmonique blanking 2 ($+2f_H$)** | **14.3650 MHz** | **$+135.00\text{ kHz}$** | **-48.5 dBc** | Hors bande 20m |
| **Harmonique 2 RF ($2 f_c$)** | **28.460 MHz** | $+14.23\text{ MHz}$ | **-42.0 dBc** | Bande 10m (Harmonique RF) |

---

### Hypothèse 2 : Mode Hors-Bande $800\times 2000$ @ 60 Hz ($f_H = 125.0\text{ kHz}$)

* **Timings vidéo :** $800\times 2000$, $H_{\text{total}} = 960$, $V_{\text{total}} = 2083$, $PCLK = 120.00\text{ MHz}$.
* **Fréquence ligne :** $f_H = 120.00\text{ MHz} / 960 = \mathbf{125.000\text{ kHz}}$.
* **Avantage spectral décisif :** L'harmonique supérieure de découpage est repoussée **strictement en dehors de la bande des 20 mètres**.
* **Fidélité locale :** Excellente (PSNR de **$16.62\text{ dB}$**, corrélation $> 95.5\%$, zéro trame en retard, zéro pente).

| Composante Fréquentielle | Fréquence Mesurée | Écart vs Porteuse | Niveau Relatif (dBc) | Classification Bande 20m |
| :--- | :--- | :--- | :--- | :--- |
| **Porteuse SSTV utile** | **14.230062 MHz** | $0\text{ kHz}$ | **0.0 dBc** (Référence) | **Signal désiré (SSTV)** |
| **Raie de blanking haute ($+f_H$)** | **14.355062 MHz** | **$+125.00\text{ kHz}$** | **-39.2 dBc** | ✅ **STRICTEMENT HORS BANDE 20M (> 14.350 MHz)** |
| **Raie de blanking basse ($-f_H$)** | **14.105062 MHz** | **$-125.00\text{ kHz}$** | **-39.5 dBc** | Segment CW/Numérique (Loin de la phonie) |
| **Harmonique blanking 2 ($+2f_H$)** | **14.480062 MHz** | **$+250.00\text{ kHz}$** | **-49.8 dBc** | ✅ Hors bande 20m |
| **Harmonique blanking 2 ($-2f_H$)** | **13.980062 MHz** | **$-250.00\text{ kHz}$** | **-50.1 dBc** | ✅ Hors bande 20m (< 14.000 MHz) |
| **Sous-bande Phonie ($14.150 - 14.350$)**| — | — | **Aucune raie** | ✅ **100 % Propre et silencieuse** |

---

### Origine physique du découpage par le blanking

Le contrôleur matériel CRTC de la carte graphique force les convertisseurs DAC au niveau noir (0.0 V) pendant les porches de synchronisation horizontale :
* En 1080p @ 60 Hz : 280 pixels sur 2200 sont à 0 V (rapport cyclique utile $D = 0.8727$, périodicité $67.5\text{ kHz}$).
* En $800\times 2000$ @ 60 Hz : 160 pixels sur 960 sont à 0 V (rapport cyclique utile $D = 0.8333$, périodicité $125.0\text{ kHz}$).

Ce créneau d'amplitude découpe le signal radio utile et crée des bandes latérales d'amplitude théorique :
$$\frac{A(f_c \pm n f_H)}{A(f_c)} = \left| \frac{\sin(\pi n D)}{\pi n D} \right| \approx -17\text{ dBc à } -34\text{ dBc}$$

---

## 3. Contraintes Réglementaires (ANFR / ITU-R) selon l'Hypothèse

### Rappel des exigences sur les rayonnements non essentiels

Selon l'**ITU-R SM.329** et la réglementation **ANFR/ARCEP** en France pour le service radioamateur en bande décamétrique (HF < 30 MHz) :
* L'atténuation minimale des rayonnements non essentiels doit être de **$43\text{ dBc}$** (et typiquement $> 50\text{ dBc}$ pour les puissances de $10\text{ W}$ à $100\text{ W}$).
* **Aucune émission hors-bande non atténuée** n'est tolérée au-delà des limites du plan de bande officiel (14.000 à 14.350 MHz).

### Impact sur le plan de bande des 20 mètres

```
             PLAN DE BANDE 20M (14.000 - 14.350 MHz)
  14.000         14.070        14.112              14.230        14.350 MHz
────┼──────────────┼─────────────┼───────────────────┼─────────────┼──────►
    │   CW PUR     │  DIGIMODES  │    PHONIE SSB     │ SSTV D'APPEL│ HORS BANDE
    │              │  (PSK, FT8) │                   │ (Martin 1)  │

[Mode 1080p]                      ▲                 ▲      ▲
Raies à ±67.5 kHz :            -f_H (14.1625)      fc    +f_H (14.2975)
                               (En plein SSB DX !)       (En plein SSB !)

[Mode 800x2000]     ▲                               ▲                    ▲
Raies à ±125 kHz : -f_H (14.105)                   fc                  +f_H (14.355)
                   (Segment CW)                                        (HORS BANDE !)
```

---

## 4. Recommandations de Filtrage Adaptées aux Deux Hypothèses

Le choix de l'hypothèse d'émission change radicalement la complexité du filtre RF à fabriquer.

### Schéma synoptique de la chaîne d'émission

```
┌────────────────────────────────────────────────────────┐
│             GPU RAMDAC (GeForce GT 630)                │
│             Sortie VGA Broches 1 et 6                  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  ÉTAGE D'ADAPTATION 75 Ω ➔ 50 Ω & DÉCOUPLAGE DC       │
│  - Test SDR direct : Pad en L (43Ω/82Ω) + Atténuateur  │
│  - Liaison PA / Émission : Tore UNUN 1.22:1 sans perte │
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
   [ Si Hypothèse 1 : 1080p ]   [ Si Hypothèse 2 : 800x2000 ]
              ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│   BRANCHE A : FILTRE      │   │   BRANCHE B : FILTRE      │
│   À QUARTZ EN ÉCHELLE     │   │   PASSE-BANDE LC OU CAUER │
│   4 pôles Cohn (BPF 3kHz) │   │   3 résonateurs T37-6     │
│   Atténuation @ 67.5 kHz  │   │   Atténuation @ 125 kHz   │
│   > 55 dBc indispensable  │   │   > 45 dBc facile         │
└─────────────┬─────────────┘   └─────────────┬─────────────┘
              │                               │
              └─────────────┬─────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  ÉTAGE LINÉAIRE : DRIVER CLASSE A + PA LINEAIRE QRP    │
│  Préampli MMIC + MOSFET (RD16HHF1 ou IRF510)           │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  FILTRE PASSE-BAS HARMONIQUE LPF 7 PÔLES (fc = 15 MHz) │
│  Suppression définitive des harmoniques H2 et H3       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
                     [ ANTENNE 50 Ω ]
```

---

### Étage commun : Découplage DC et adaptation d'impédance 75 Ω ➔ 50 Ω

La sortie VGA (Broche 1) présente une composante continue médiane de $+0.35\text{ V}$ et une impédance caractéristique de $75\ \Omega$. Deux cas d'usage se distinguent :

#### Cas 1 : Connexion directe au banc de mesure / SDRplay RSP1 (Pad en L Minimum Loss)

Pour raccorder directement la sortie VGA à un récepteur sensible (SDRplay RSP1, RTL-SDR) sans risque de saturation, on utilise un **Pad en L** combiné à un condensateur de découplage série :

```text
               C_DC = 100 nF        R_s = 43 Ω (E24) ou 47 Ω (E12)
VGA In (75 Ω) o─────┤├───┬───────────/\/\/\──────────┬─────o RF Out (50 Ω vers SDR)
(Broche 1)               │                           │
                        (Non                         [ ] R_p = 82 Ω
                       connecté)                      │
                                                     ---
VGA GND (Broche 6) o─────────────────────────────────┴─────o GND SMA (Blindage)
```

* **Découplage continu :** $C_{\text{DC}} = 100\text{ nF}$ (pastille céramique "104") en série sur la ligne de signal bloque à $100\%$ le $+0.35\text{ V}$ DC ($X_C \approx 0.11\ \Omega$ à $14.23\text{ MHz}$).
* **Adaptation bilatérale (mesures ngspice) :**
  * Côté VGA ($75\ \Omega$) : $Z_{\text{in}} = 74.1\ \Omega \implies S_{11} = -44\text{ dB}$, $\text{ROS} = 1.01 : 1$.
  * Côté SDR ($50\ \Omega$) : $Z_{\text{out}} = 48.4\ \Omega \implies S_{22} = -36\text{ dB}$, $\text{ROS} = 1.03 : 1$.
* **Pertes d'insertion :** $5.84\text{ dB}$ (optimum théorique pour une adaptation résistive pure).
* **Atténuation complémentaire :** Compléter par un atténuateur RF $50\ \Omega$ coaxial de **$20\text{ dB}$ à $30\text{ dB}$** devant l'entrée SMA du RSP1 pour opérer dans la zone de linéarité idéale de l'ADC ($-30\text{ dBm}$).

#### Cas 2 : Connexion vers chaîne d'émission (Filtre + PA d'émission)

À l'inverse d'une mesure SDR où l'on cherche à atténuer, une chaîne d'émission doit préserver l'intégralité du faible signal utile du RAMDAC (~$0\text{ dBm}$ / $1\text{ mW}$) :
* **Tolérance du port VGA :** Le contrôleur vidéo VGA tolère très bien un ROS modéré sans dommage matériel.
* **Solutions sans pertes résistives :**
  1. **Autotransformateur UNUN sur tore ferrite (FT37-43) :** 11 spires au total avec prise à 9 spires (rapport de transformation $\sqrt{1.5} \approx 1.22:1$, pertes $< 0.3\text{ dB}$).
  2. **Attaque directe du filtre passe-bande :** Dimensionner l'impédance du premier étage résonateur du filtre LC ou Cohn directement à $75\ \Omega$, avec sortie résonateur adaptée à $50\ \Omega$.

---

### Branche A (Pour Hypothèse 1 : 1080p @ 60 Hz) : Filtrage ultra-sélectif à quartz

Dans l'Hypothèse 1, les raies parasites se trouvent à seulement **$\pm 67.5\text{ kHz}$** de la porteuse utile, tout en étant situées dans la bande amateur. Un filtre LC classique nécessiterait un coefficient de surtension irréaliste ($Q > 250$).

#### Solution requise : Le Filtre à Quartz en Échelle (Cohn 4 pôles)
* **Topologie :** 4 quartz identiques taillés à $14.230\text{ MHz}$ (format HC-49/US ou HC-49/U) montés en série, couplés par des condensateurs céramiques C0G vers la masse :
  * $C_1 = C_4 = 47\text{ pF}$ (terminaisons)
  * $C_2 = C_3 = 82\text{ pF}$ (inter-résonateurs)
* **Bande passante à $-3\text{ dB}$ :** $\approx 2.8\text{ kHz}$ (parfaitement ajustée au spectre Martin 1).
* **Atténuation à $\pm 67.5\text{ kHz}$ :** **$> 60\text{ dB}$**.
* **Résultat :** Les raies parasites à $14.1625\text{ MHz}$ et $14.2975\text{ MHz}$ chutent à **$<-75\text{ dBc}$**, largement sous le plancher de bruit.

---

### Branche B (Pour Hypothèse 2 : Mode Hors-Bande 125 kHz) : Filtrage LC standard ou Cauer

Dans l'Hypothèse 2, l'harmonique supérieure est à **$14.355\text{ MHz}$** (hors bande) et l'inférieure à **$14.105\text{ MHz}$** (écart de $125\text{ kHz}$). La réjection des raies ne nécessite plus de découper l'audio avec un quartz à bande étroite.

Deux solutions simples et économiques sont possibles :

#### Option B1 : Filtre Passe-Bande LC 20m 3 Résonateurs (Recommandé)
* **Topologie :** 3 circuits oscillants parallèles LC couplés par capacités de tête :
  * Tores : **Amidon T37-6** ou **T50-6** (jaune, poudre de fer, faible perte en HF).
  * Inductances : $L_1 = L_2 = L_3 = 1.3\ \mu\text{H}$ (18 spires de fil émaillé 0.4 mm sur T37-6).
  * Capacités parallèles : $C = 91\text{ pF}$ (ajustable avec trimmer $10-60\text{ pF}$ en parallèle).
  * Capacités de couplage inter-étages : $C_c = 2.7\text{ pF}$ (C0G).
* **Bande passante à $-3\text{ dB}$ :** $250\text{ kHz}$ ($14.100 - 14.350\text{ MHz}$).
* **Atténuation à $+125\text{ kHz}$ ($14.355\text{ MHz}$) :** $\approx 22\text{ dB}$.
* Combiné à l'atténuation native du DAC ($-39\text{ dBc}$), la raie hors-bande tombe à **$-61\text{ dBc}$**, ce qui dépasse largement les exigences de l'ANFR ($-43\text{ dBc}$).

#### Option B2 : Filtre Passe-Bas Elliptique (Cauer 7 pôles avec encoche à 14.355 MHz)
* En intégrant des résonances parallèles (trappes série) accordées précisément sur **$14.355\text{ MHz}$** et **$28.46\text{ MHz}$**, un filtre Cauer permet de faire chuter la raie hors-bande de plus de **$40\text{ dB}$** dès la sortie de la bande amateur, tout en conservant une bande passante plate sur toute la bande des 20 m.

---

### Matrice comparative des deux solutions de filtrage

| Critère | Hypothèse 1 : 1080p @ 60 Hz | Hypothèse 2 : $800\times 2000$ @ 60 Hz |
| :--- | :---: | :---: |
| **Fréquence ligne $f_H$** | $67.50\text{ kHz}$ | **$125.00\text{ kHz}$** |
| **Position raie haute** | $14.2975\text{ MHz}$ *(En bande SSB)* | **$14.3550\text{ MHz}$ *(Hors bande amateur)*** |
| **Type de filtre obligatoire** | **Filtre à quartz en échelle (Cohn)** | **Filtre LC classique 3 pôles (Tores T37-6)** |
| **Composants critiques** | 4 quartz identiques taillés sur mesure | Inductances bobinées main + condensateurs ordinaires |
| **Complexité de réglage** | Délicat (adaptation d'impédance Cohn) | **Facile (réglage aux trimmers sur analyseur/SDR)** |
| **Bande passante RF** | Fixe ($\pm 1.5\text{ kHz}$ autour du quartz) | **Large ($14.00 - 14.35\text{ MHz}$, agile en fréquence)** |
| **PSNR image décodée** | **$19.56\text{ dB}$** | **$16.62\text{ dB}$** |
| **Recommandation opérationnelle** | **Banc de mesure / Laboratoire** | **Émission réelle sur antenne (Conforme et simple)** |

---

### Étages d'amplification linéaire (Classe A / AB QRP)

Le signal en sortie du filtre (environ $-4\text{ dBm}$ / $0.4\text{ mW}$) doit être amplifié sans aucune distorsion d'intermodulation :

1. **Préamplificateur linéaire :**
   * Circuit intégré MMIC **Mini-Circuits Gali-5+**, **MAR-6** ou transistor bipolaire HF **2N5109** / **BFG591** en Classe A pure (+17 dB de gain, IP3 de sortie élevé).
2. **Amplificateur final QRP (1 W à 5 W PEP) :**
   * Transistor MOSFET RF linéaire **Mitsubishi RD16HHF1** polarisé avec un courant de repos suffisant ($I_{dq} = 500\text{ mA}$) sous 13.8 V, ou étage push-pull à deux **IRF510**.
   * **Interdiction absolue des amplificateurs Classe C** (réservés à la FM/CW pure), qui régénéreraient immédiatement toutes les raies de découpage par intermodulation.

---

## 5. Protocole de Validation et Mesures Avant Émission sur Antenne

Avant d'émettre en l'air sur antenne sous votre indicatif radioamateur, validez impérativement les critères suivants sur **charge fictive $50\ \Omega$** :

1. **Mesure de puissance de la porteuse pure :**
   ```bash
   # En mode Hors-Bande (Hypothèse 2) :
   ssh loic@192.168.1.26 "cd ~/projets/vga-hamradio && DISPLAY=:0 .venv/bin/python3 vga_sstv.py --cw -f 14.230e6 --duration 10.0"
   ```
2. **Contrôle spectral sur analyseur ou récepteur SDR (Span 500 kHz) :**
   * **Si Hypothèse 1 (1080p) :** Vérifiez que les raies à $14.1625\text{ MHz}$ et $14.2975\text{ MHz}$ sont sous **$-50\text{ dBc}$** après le filtre à quartz.
   * **Si Hypothèse 2 ($800\times 2000$) :** Vérifiez que la raie hors-bande à $14.355\text{ MHz}$ est sous **$-45\text{ dBc}$** après le filtre LC, et qu'aucune raie mesurable n'apparaît entre $14.150$ et $14.350\text{ MHz}$.
3. **Contrôle des harmoniques lointaines (Span 50 MHz) :**
   * L'harmonique 2 ($28.46\text{ MHz}$) et l'harmonique 3 ($42.69\text{ MHz}$) doivent être atténuées d'au moins **$-50\text{ dBc}$** par le filtre passe-bas final.
4. **Écoute de contrôle locale :**
   * Écoutez sur un second récepteur HF calé sur $14.1625\text{ MHz}$ et $14.2975\text{ MHz}$ : aucun sifflement ni perturbation ne doit être audible pendant une transmission complète de mire SSTV.

Une fois ces critères validés, votre station est **100 % conforme aux exigences de l'ANFR et de l'IARU**.
