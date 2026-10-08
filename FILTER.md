# 📡 Rapport d'Analyse Spectrale & Guide de Filtrage RF : Émetteur VGA-SDR

> **Projet :** Émission Radio SSTV (Martin 1) / SDR via GPU RAMDAC (DDS GLSL)  
> **Auteur :** F4JXQ / Laboratoire d'expérimentation GPU SDR  
> **Cible RF :** Bande des 20 mètres (14.230 MHz USB)  
> **Fichier de référence :** `FILTER.md`

---

## 📑 Sommaire

1. [Contexte et Architecture du Système](#1-contexte-et-architecture-du-système)
2. [Diagnostic Spectral des Enregistrements I/Q Réels](#2-diagnostic-spectral-des-enregistrements-iq-réels)
   - [Analyse de `sstv_full.cf32` et `capture_cw.cf32`](#analyse-de-sstv_fullcf32-et-capture_cwcf32)
   - [Origine physique des raies parasites](#origine-physique-des-raies-parasites)
   - [Démonstration mathématique de la modulation de blanking](#démonstration-mathématique-de-la-modulation-de-blanking)
3. [Non-Conformité Réglementaire (ANFR / ITU-R)](#3-non-conformité-réglementaire-anfr--itu-r)
   - [Normes sur les rayonnements non essentiels](#normes-sur-les-rayonnements-non-essentiels)
   - [Impact concret sur le plan de bande des 20 mètres](#impact-concret-sur-le-plan-de-bande-des-20-mètres)
   - [Pourquoi un filtre passe-bas standard (LPF) est inefficace](#pourquoi-un-filtre-passe-bas-standard-lpf-est-inefficace)
4. [Solutions Pratiques de Filtrage & Traitement RF](#4-solutions-pratiques-de-filtrage--traitement-rf)
   - [Schéma synoptique de la chaîne d'émission complète](#schéma-synoptique-de-la-chaîne-démission-complète)
   - [Étage 1 : Blocage DC et adaptation d'impédance 75 Ω ➔ 50 Ω](#étage-1--blocage-dc-et-adaptation-dimpédance-75-ω--50-ω)
   - [Étage 2 : Filtrage passe-bande étroit (BPF / Filtre à quartz)](#étage-2--filtrage-passe-bande-étroit-bpf--filtre-à-quartz)
   - [Étage 3 : Déport logiciel des raies parasites (Mode 120 Hz CVT-RB)](#étage-3--déport-logiciel-des-raies-parasites-mode-120-hz-cvt-rb)
   - [Étage 4 : Amplification strictement linéaire (Classe A / AB QRP)](#étage-4--amplification-strictement-linéaire-classe-a--ab-qrp)
5. [Protocole de Validation et Mesures Avant Émission sur Antenne](#5-protocole-de-validation-et-mesures-avant-émission-sur-antenne)

---

## 1. Contexte et Architecture du Système

Le projet `vga-hamradio` détourne le triple convertisseur numérique-analogique (**RAMDAC 8-bit**) d'une carte graphique NVIDIA pour générer directement un signal radiofréquence modulé en **Bande Latérale Supérieure (BLU / USB)** à $14.230\text{ MHz}$ :

1. **Horloge matérielle :** Le RAMDAC est cadencé par un quartz vidéo autonome ($f_{\text{pixel}} = 148.50\text{ MHz}$ en mode 1080p @ 60Hz standard, ou $285.50\text{ MHz}$ en mode 1080p @ 120Hz).
2. **Génération DDS & Modulation :** Un fragment shader OpenGL calcule à chaque pixel la phase d'une onde porteuse et la multiplie par les composantes en quadrature $I(t)$ et $Q(t)$ de l'audio SSTV pré-calculé :
   $$\text{RF}(t) = I(t)\cos(\theta_c(t)) - Q(t)\sin(\theta_c(t))$$
3. **Sortie Physique :** Le signal analogique $0.0\text{ V} - 0.7\text{ V}$ est extrait entre la **Broche 1** (Canal Rouge) et la **Broche 6** (Masse RF) de la prise DE-15 (VGA).

Bien que cette technique fournisse un signal d'un excellent rapport signal/bruit local ($> 65\text{ dB}$ mesuré en champ proche), l'architecture de balayage vidéo analogique introduit intrinsèquement des bandes latérales indésirables qui interdisent toute connexion directe à une antenne d'émission sans étage de filtrage dédié.

---

## 2. Diagnostic Spectral des Enregistrements I/Q Réels

### Analyse de `sstv_full.cf32` et `capture_cw.cf32`

Une analyse FFT multi-résolution sur les captures I/Q réalisées au SDRplay RSP1 (taux d'échantillonnage de $250\text{ kSps}$ et $2.0\text{ MSps}$) révèle la structure spectrale suivante :

| Composante Fréquentielle | Fréquence Mesurée | Écart vs Porteuse ($14.230\text{ MHz}$) | Niveau Absolu | Atténuation Relative (dBc) | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Porteuse SSTV utile** | **14.2315 - 14.2324 MHz** | $+1.5\text{ kHz}$ à $+2.4\text{ kHz}$ (Audio Martin 1) | **+65.7 dB** | **0.0 dBc** (Référence) | **Signal désiré** |
| **Raie de blanking basse ($ -f_H $)** | **14.1625 MHz** | **$-67.50\text{ kHz}$** | **+27.0 dB** | **-38.7 dBc** | **Émission parasite non conforme** |
| **Raie de blanking haute ($ +f_H $)** | **14.2975 MHz** | **$+67.50\text{ kHz}$** | **+27.9 dB** | **-37.8 dBc** | **Émission parasite non conforme** |
| **Harmonique blanking 2 ($ -2f_H $)** | **14.0950 MHz** | **$-135.00\text{ kHz}$** | **+16.8 dB** | **-48.9 dBc** | Rayonnement non essentiel |
| **Harmonique blanking 2 ($ +2f_H $)** | **14.3650 MHz** | **$+135.00\text{ kHz}$** | **+17.2 dB** | **-48.5 dBc** | Rayonnement non essentiel |
| **Harmonique blanking 3 ($ \pm 3f_H $)**| **14.0275 / 14.4325 MHz** | **$\pm 202.50\text{ kHz}$** | **+13.7 dB** | **-52.0 dBc** | Rayonnement non essentiel |
| **Spurs de régulateur VRM GPU** | Décalages multiples de $\sim 257\text{ kHz}$ | $-347\text{ kHz}$, $-90\text{ kHz}$, $+167\text{ kHz}$ | $\approx +23\text{ dB}$ | **-42.0 dBc** | Bruit de hachage d'alimentation |

### Origine physique des raies parasites

1. **Le hachage par le blanking vidéo (67.5 kHz) :**
   Dans la norme VGA 1080p @ 60Hz :
   * Une ligne vidéo totale dure $H_{\text{total}} = 2200$ pixels.
   * La zone active affichée par OpenGL ne compte que $H_{\text{active}} = 1920$ pixels.
   * Les $280$ pixels restants correspondent aux porches avant/arrière (*front/back porch*) et à l'impulsion de synchronisation horizontale. Pendant cet intervalle, **le contrôleur matériel CRTC de la carte graphique force le DAC au niveau 0 V**.
   * Le signal radio n'est donc pas continu dans le temps : il est **découpé en créneaux** à la fréquence ligne exacte de $67.500\text{ kHz}$.

2. **Le hachage par le blanking vertical (60 Hz) :**
   Sur les $V_{\text{total}} = 1125$ lignes, seules $1080$ sont affichées. Les $45$ lignes de blanking vertical introduisent une modulation d'amplitude à $60\text{ Hz}$ qui élargit légèrement le pied de chaque raie.

3. **L'ondulation de découpage des VRM du GPU (~257 kHz) :**
   Les convertisseurs Buck d'alimentation du processeur graphique et de la mémoire VRAM injectent une micro-ondulation résiduelle sur les rails d'alimentation analogiques du RAMDAC, provoquant une modulation de phase et d'amplitude parasite espacée d'environ $257\text{ kHz}$.

### Démonstration mathématique de la modulation de blanking

Le signal émis en sortie de broche VGA est le produit du signal RF calculé dans le shader $s(t) = \cos(\omega_c t)$ et de la fonction de porte vidéo périodique $p(t)$ de période $T_H = \frac{1}{67500}\text{ s}$ :
$$r(t) = s(t) \cdot p(t)$$

Avec un rapport cyclique $D = \frac{1920}{2200} \approx 0.8727$, la décomposition en série de Fourier de la porte rectangulaire donne :
$$p(t) = D + \sum_{n=1}^{+\infty} 2 D \, \operatorname{sinc}(n D) \cos(n \omega_H t)$$

Le produit avec la porteuse génère deux raies latérales à chaque harmonique $n$ de la fréquence ligne :
$$\frac{A(f_c \pm n f_H)}{A(f_c)} = \left| \operatorname{sinc}(n D) \right| = \left| \frac{\sin(\pi n D)}{\pi n D} \right|$$

Pour la première harmonique ($n = 1$) avec $D = 0.8727$ :
$$\frac{A_1}{A_0} = \left| \frac{\sin(0.8727 \pi)}{0.8727 \pi} \right| = \frac{\sin(157.09^\circ)}{2.7417} = \frac{0.3892}{2.7417} \approx 0.14195$$

En décibels :
$$20 \log_{10}(0.14195) \approx \mathbf{-16.96\text{ dBc}}$$

*Conclusion :* Théoriquement, le premier couple de raies latérales de blanking est à seulement **$-17\text{ dBc}$** de la porteuse. Sur notre banc expérimental, l'impédance de ligne et la bande passante du convertisseur atténuent ce niveau à **$-34\text{ dBc}$**, ce qui reste largement au-dessus du seuil légal.

---

## 3. Non-Conformité Réglementaire (ANFR / ITU-R)

### Normes sur les rayonnements non essentiels

Selon les recommandations de l'**ITU-R SM.329**, l'Appendice 3 du **Règlement des Radiocommunications (RR)** et les décisions de l'**ARCEP / ANFR** en France :

* **Domaine HF (en dessous de 30 MHz) pour le service amateur :**
  Tout rayonnement non essentiel (*spurious emission*) doit être atténué d'au moins :
  $$\text{Atténuation minimale} = \mathbf{43\text{ dBc}} \quad (\text{ou } 43 + 10 \log_{10}(P_{\text{PEP}})\text{ dBc})$$
  *(Pour un émetteur de $10\text{ W}$ à $100\text{ W}$, cette exigence monte à $-50\text{ dBc}$, voire $-60\text{ dBc}$).*

### Impact concret sur le plan de bande des 20 mètres

La bande radioamateur des 20 mètres s'étend de **14.000 MHz à 14.350 MHz** :
* Fréquence SSTV d'appel internationale : **14.230 MHz**.
* **Raie parasite $-f_H$ (14.1625 MHz) :** Elle tombe en plein dans le segment **Phonie SSB DX** (14.150 - 14.200 MHz). À seulement $-34\text{ dBc}$, une émission de quelques watts brouillerait sévèrement les liaisons phonie à longue distance.
* **Raie parasite $-2f_H$ (14.0950 MHz) :** Elle tombe dans le segment réservé aux **modes numériques étroits et balises** (14.070 - 14.100 MHz).
* **Raie parasite $+f_H$ (14.2975 MHz) :** Elle tombe dans le segment phonie haute de la bande 20m.

### Pourquoi un filtre passe-bas standard (LPF) est inefficace

Un filtre passe-bas 7 pôles classique (coupure à $15\text{ MHz}$ ou $30\text{ MHz}$) :
* Supprime parfaitement les harmoniques RF d'ordre 2 ($28.46\text{ MHz}$), d'ordre 3 ($42.69\text{ MHz}$) et les images d'échantillonnage du DAC ($134.27\text{ MHz}$).
* **MAIS** il laisse passer **100 % de la puissance des raies à $\pm 67.5\text{ kHz}$**, car $14.162\text{ MHz}$ et $14.297\text{ MHz}$ sont en plein dans sa bande passante.

> [!WARNING]
> Un simple filtre passe-bas (LPF) ne suffit absolument pas pour émettre en l'air. Un **filtre passe-bande étroit (BPF)** ou un **filtre à quartz** est strictement indispensable.

---

## 4. Solutions Pratiques de Filtrage & Traitement RF

Pour rendre l'émetteur parfaitement propre et conforme avant injection dans un amplificateur de puissance et une antenne, voici la chaîne de conditionnement recommandée :

### Schéma synoptique de la chaîne d'émission complète

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             CARTE GRAPHIQUE (GPU NVIDIA)                         │
│  Sortie VGA Broche 1 (Rouge, 75 Ω) + Broche 6 (GND)                              │
│  Signal : 14.230 MHz USB @ -3 dBm + Offset DC 0.35 V + Raies blanking à ±67.5kHz  │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ÉTAGE 1 : DÉCOUPLAGE DC & ADAPTATION D'IMPÉDANCE 75 Ω ➔ 50 Ω                    │
│  - Condensateur céramique NP0/C0G 100 nF (blocage DC)                            │
│  - Atténuateur asymétrique résistif en Pi 3 dB (75 Ω entrée / 50 Ω sortie)       │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ÉTAGE 2 : FILTRAGE PASSE-BANDE ULTRA-SÉLECTIF (BPF 20m)                         │
│  Option A (Idéale) : Filtre à quartz en échelle 4 pôles (Cohn/Dishal)            │
│  Option B (LC)     : Filtre passe-bande 3 résonateurs LC à tores T37-6 (Q > 40)  │
│  Rejet des raies à ±67.5 kHz : > -50 dBc                                         │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ÉTAGE 3 : DRIVER LINÉAIRE CLASSE A (QRP)                                        │
│  - Préamplificateur MMIC large bande (ex: Gali-5+, MAR-6 ou 2N2222A / 2N5109)   │
│  - PA linéaire Classe A/AB (ex: MOSFET RD16HHF1 ou push-pull IRF510)             │
│  - Niveau de sortie : 1 W à 5 W PEP                                              │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ÉTAGE 4 : FILTRE PASSE-BAS HARMONIQUE LPF 7 PÔLES                               │
│  - Filtre Chebyshev / Butterworth fc = 15.0 MHz (Coupure de H2, H3 et Nyquist)    │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
                                   [ ANTENNE 50 Ω ]
```

---

### Étage 1 : Blocage DC et adaptation d'impédance 75 Ω ➔ 50 Ω

La sortie VGA présente une impédance caractéristique nominale de $75\ \Omega$ et une tension continue médiane de $+0.35\text{ V}$ ($0.7\text{ V}$ crête-à-crête centré).

1. **Blocage DC :**
   Un condensateur céramique multicouche (MLCC) C0G/NP0 de **$100\text{ nF}$** est inséré en série. Son impédance à $14.23\text{ MHz}$ est quasi nulle :
   $$|Z_C| = \frac{1}{2\pi \cdot 14.23 \cdot 10^6 \cdot 100 \cdot 10^{-9}} \approx 0.11\ \Omega$$

2. **Atténuateur résistif d'adaptation en $\Pi$ ($75\ \Omega \to 50\ \Omega$, atténuation $3.5\text{ dB}$) :**
   Il assure une charge strictement résistive pour le DAC tout en adaptant la ligne vers les appareils de mesure et filtres $50\ \Omega$.

```
         C_DC = 100 nF        R_s = 22 Ω
VGA In o─────┤├───┬─────────────/\/\/\─────────────┬─────o RF Out (50 Ω)
(75 Ω)            │                                │
                 [ ] R_in = 150 Ω                 [ ] R_out = 100 Ω
                  │                                │
GND    o──────────┴────────────────────────────────┴─────o GND
```

---

### Étage 2 : Filtrage passe-bande étroit (BPF / Filtre à quartz)

Pour éliminer des raies situées à seulement **$67.5\text{ kHz}$** de la fréquence centrale tout en conservant la bande passante utile Martin 1 ($14.2312 - 14.2324\text{ MHz}$, soit $\approx 1.2\text{ kHz}$ de bande passante), deux approches matérielles sont viables :

#### Option A : Le Filtre à Quartz en Échelle (Crystal Ladder Filter) — Recommandé

C'est la solution la plus performante et la moins onéreuse :
* **Composants :** 4 quartz identiques bon marché au format HC-49/S ou HC-49/U.
* **Choix de la fréquence :** Quartz taillés sur $14.31818\text{ MHz}$ (fréquence standard NTSC très commune, tirée de quelques kHz par capacité) ou quartz commandés sur mesure à $14.230\text{ MHz}$.
* **Topologie :** Filtre en échelle de Cohn (tous quartz de même fréquence en série, avec condensateurs shunt vers la masse de $33\text{ pF}$ à $68\text{ pF}$).
* **Performances :**
  * Bande passante à $-3\text{ dB}$ : $\approx 3.0\text{ kHz}$.
  * Réjection à $\pm 20\text{ kHz}$ : $> 45\text{ dB}$.
  * **Réjection à $\pm 67.5\text{ kHz}$ : $> 60\text{ dB}$.**
* Les raies de blanking et les bruits d'alimentation disparaissent totalement sous le plancher de bruit thermique.

#### Option B : Le Filtre Passe-Bande LC Multipolaire à Tores Ferrite

Si l'émission doit être modulable sur l'ensemble de la bande des 20 mètres sans changer de quartz :
* **Composants :** 3 résonateurs LC couplés en haut par de petites capacités ($1.5\text{ pF} - 3.3\text{ pF}$).
* **Inductances :** Bobinages sur tores poudre de fer **Amidon T37-6** ou **T50-6** (jaune, matériau adapté à la bande 3-30 MHz) pour obtenir $Q > 150$.
* **Bande passante :** Conçue pour $150\text{ kHz}$ à $-3\text{ dB}$ ($14.175 - 14.325\text{ MHz}$).
* Pour obtenir $-43\text{ dBc}$ de réjection à $67.5\text{ kHz}$ avec du LC pur, il faut un filtre d'ordre élevé (5 résonateurs couplés) avec réglage fin par condensateurs ajustables (*trimmers*).

---

### Étage 3 : Déport logiciel des raies parasites (Mode 120 Hz CVT-RB)

Le script de configuration vidéo [`setup_display.sh`](file:///home/loic/projets/vga-hamradio/setup_display.sh) intègre nativement un mode alternatif haute fréquence :

```bash
DISPLAY=:0 ./setup_display.sh -o VGA-1 -r 120
```

Dans ce mode :
* **Pixel Clock :** $285.50\text{ MHz}$
* **Modeline :** $1920\times 1080$, $H_{\text{total}} = 2080$, $V_{\text{total}} = 1144$ (CVT-RB : *Reduced Blanking*)
* **Fréquence ligne $f_H$ :**
  $$f_H = \frac{285.50\text{ MHz}}{2080} = \mathbf{137.26\text{ kHz}}$$

#### Bénéfice immédiat :
* Les premières raies parasites sont rejetées deux fois plus loin de la porteuse : à **$\pm 137.26\text{ kHz}$** (soit **14.0927 MHz** et **14.3672 MHz**).
* L'écart plus important facilite considérablement la conception du filtre passe-bande passif LC (la pente de coupure requise passe de $60\text{ dB/décade}$ à moins de $30\text{ dB/décade}$).

---

### Étage 4 : Amplification strictement linéaire (Classe A / AB QRP)

La puissance RF brute délivrée par le RAMDAC sur une charge adaptée de $50\ \Omega$ est :
$$V_{\text{RMS}} \approx \frac{0.7\text{ V}}{2\sqrt{2}} \approx 0.25\text{ V}_{\text{RMS}} \implies P = \frac{V^2}{R} = \frac{0.25^2}{50} \approx 1.25\text{ mW} \quad (\approx \mathbf{+1\text{ dBm}})$$

Après passage dans l'atténuateur et le filtre passe-bande (pertes d'insertion typiques de $4$ à $6\text{ dB}$), le niveau disponible est d'environ **$-4\text{ dBm}$ ($0.4\text{ mW}$)**.

Pour émettre en QRP ($1\text{ W}$ à $5\text{ W}$) :
1. **Interdiction absolue de la Classe C :** La modulation SSTV USB contient une modulation d'amplitude et de phase continue. Un amplificateur non linéaire classe C régénérerait immédiatement toutes les raies d'intermodulation et de blanking.
2. **Étage préamplificateur :** Un composant MMIC (ex: Mini-Circuits Gali-5+ ou MAR-6) ou un transistor bipolaire HF faible bruit (2N5109 ou BFG591) polarisé en **Classe A pure** (+15 à +20 dB de gain).
3. **Étage de puissance final :** Un MOSFET de puissance RF linéaire de type **Mitsubishi RD16HHF1** polarisé avec un courant de repos suffisant ($I_{dq} \approx 500\text{ mA}$) ou un push-pull double IRF510.

---

## 5. Protocole de Validation et Mesures Avant Émission sur Antenne

Avant tout raccordement à une antenne extérieure sous votre indicatif radioamateur, effectuez les vérifications suivantes sur **charge fictive $50\ \Omega$** :

1. **Mesure de puissance de la porteuse pure :**
   ```bash
   DISPLAY=:0 python3 vga_sstv.py --cw -f 14.230e6 --fullscreen --duration 10.0
   ```
   Mesurez la puissance au wattmètre RF ou millivoltmètre de crête.

2. **Contrôle de réjection spectrale sur SDR / Analyseur de spectre :**
   * Réglez la bande de visualisation sur un span de **$500\text{ kHz}$** centré sur $14.230\text{ MHz}$.
   * Vérifiez que le niveau de la raie à $14.1625\text{ MHz}$ et $14.2975\text{ MHz}$ est au minimum à **$-45\text{ dB}$** sous le sommet du signal utile.
   * Élargissez le span à **$50\text{ MHz}$** pour vérifier que l'harmonique 2 ($28.46\text{ MHz}$) et l'harmonique 3 ($42.69\text{ MHz}$) sont atténuées d'au moins **$-50\text{ dBc}$**.

3. **Test d'interférence locale :**
   * Écoutez sur un second récepteur HF accordé sur la fréquence phonie $14.1625\text{ MHz}$. Aucun déclenchement de squelch ni sifflement audible ne doit être perceptible pendant une transmission complète de mire SSTV.

Une fois ces trois critères validés, votre émetteur SDR expérimental sur base GPU est 100 % conforme aux exigences de l'ANFR et de l'IARU, prêt pour des liaisons SSTV réelles en l'air.
