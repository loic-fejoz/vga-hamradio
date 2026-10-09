# 🎮 Guide du Matériel GPU : Sélection, Compatibilité & Marché de l'Occasion pour l'Émission SDR via RAMDAC

> **Projet :** Émetteur Radio SSTV (Martin 1) / SDR via GPU RAMDAC (DDS GLSL)  
> **Auteur :** Loïc Fejoz (F4JXQ) / Assistant Antigravity  
> **Date :** 9 octobre 2026  
> **Fichier de référence :** `GPU.md`

---

## 📑 Sommaire

1. [Le Critère Éliminatoire Absolu : Le RAMDAC Matériel](#1-le-critère-éliminatoire-absolu--le-ramdac-matériel)
2. [Analyse Générationnelle NVIDIA GeForce](#2-analyse-générationnelle-nvidia-geforce)
3. [Analyse Générationnelle AMD / ATI Radeon](#3-analyse-générationnelle-amd--ati-radeon)
4. [Le « Sweet Spot » Radioamateur : Pourquoi les cartes à 10 € surpassent les GPU Gaming](#4-le-sweet-spot-radioamateur--pourquoi-les-cartes-à-10--surpassent-les-gpu-gaming)
5. [Prise en Charge des Pilotes sous Linux (Nouveau vs Radeon)](#5-prise-en-charge-des-pilotes-sous-linux-nouveau-vs-radeon)
6. [Guide d'Achat d'Occasion & Matrice Comparative](#6-guide-dachat-doccasion--matrice-comparative)
7. [Analyse Économique et Compétitivité face aux SDR Dédiés (HackRF One)](#7-analyse-économique-et-compétitivité-face-aux-sdr-dédiés-hackrf-one)

---

## 1. Le Critère Éliminatoire Absolu : Le RAMDAC Matériel

Pour émettre un signal radiofréquence en bande HF (14.230 MHz) par modulation de tension, **la puce graphique doit impérativement intégrer un convertisseur numérique-analogique matériel (RAMDAC)** cadencé par son propre quartz.

### Pourquoi les écrans modernes ont tué le RAMDAC
* Les interfaces numériques modernes (**HDMI**, **DisplayPort**, **DVI-D**) ne transportent aucune tension analogique : elles transmettent des flux de paquets de données numériques sérialisés (TMDS ou micro-paquets LVDS).
* Vers 2015-2016, les fondeurs (NVIDIA et AMD) ont retiré physiquement tous les blocs de conversion analogique de leurs circuits intégrés afin de réduire la surface de silicium et la consommation.

### Le piège des adaptateurs actifs externes
* Un GPU dépourvu de RAMDAC branché à un convertisseur actif externe (dongle HDMI vers VGA ou DisplayPort vers VGA) **ne convient absolument pas** :
  1. Le signal est synthétisé par une puce tierce autonome (Realtek, Silicon Image) sur laquelle l'OS n'a aucun contrôle de registres CRTC.
  2. L'horloge d'échantillonnage n'est plus asservie au pipeline OpenGL.
  3. Des tampons internes de trame créent une gigue et détruisent la cohérence de phase nécessaire à la modulation SSB.

> [!CAUTION]
> **Règle d'or :** Le GPU doit posséder un **RAMDAC physique interne relié directement aux broches de sortie de la carte** (prise VGA DE-15 bleue ou prise DVI-I).

---

## 2. Analyse Générationnelle NVIDIA GeForce

Chez NVIDIA, la coupure a eu lieu lors du passage à l'architecture **Pascal (série GTX 1000)** en 2016.

```
       [ 2008 - 2011 ]             [ 2012 - 2014 ]             [ 2014 - 2015 ]             [ 2016+ ]
        Tesla / Fermi                  Kepler                      Maxwell                  Pascal & +
    (GT 200, 400, 500...)           (GT 600, 700)              (GTX 950, 960)            (GTX 1050, 1060...)
  ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
  │  RAMDAC NATIF INCLUS  │   │  RAMDAC NATIF INCLUS  │   │   RAMDAC SUR DVI-I    │   │ RAMDAC TOTALEMENT     │
  │    VGA & DVI-I        │   │    VGA & DVI-I        │   │   (Vérifier 4 broches)│   │ SUPPRIMÉ DU SILICIUM  │
  └───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
              │                           │                           │                           │
              ▼                           ▼                           ▼                           ▼
        ✅ COMPATIBLE               ✅ CŒUR DE CIBLE            ⚠️ COMPATIBLE DVI-I         🚫 INCOMPATIBLE
```

### Cas Pratiques d'Annonces NVIDIA d'Occasion :
* **GeForce GT 610 / GT 710 à 10 € :**  
  ✅ **Idéales.** Puce Fermi/Kepler, port VGA DE-15 direct, consommation 19 W, souvent fanless (sans ventilateur).
* **GeForce GT 630 (notre banc expérimental `my-yuno`) :**  
  ✅ **Parfaite.** Port VGA direct, RAMDAC 400 MHz cadencé à 120 ou 148,5 MHz sans gigue.
* **GeForce GTX 960 à 25 € – 30 € :**  
  ⚠️ **Compatible sous condition.** Elle possède un RAMDAC, mais utilise une prise DVI. Il faut impérativement vérifier sur la photo que la prise est un **DVI-I** (présence des 4 petites broches analogiques C1–C4 autour de la languette plate). Un adaptateur passif DVI-to-VGA à 2 € est alors requis.  
  *Inconvénients :* Consommation élevée (120 W), nécessite un connecteur PCIe 6 broches, ventilateurs bruyants.
* **GeForce GTX 1060 à 40 € :**  
  🚫 **À ÉLIMINER D'OFFICE.** L'architecture Pascal n'a aucun RAMDAC. La prise DVI est un **DVI-D numérique pur**. Même avec un adaptateur mécanique, aucun signal ne sortira sur les broches analogiques.

---

## 3. Analyse Générationnelle AMD / ATI Radeon

Chez AMD, la transition historique est rigoureusement identique. La coupure s'est faite avec l'architecture **Polaris (série RX 400 / RX 500)** en 2016.

| Famille AMD / ATI | Période | Architecture | RAMDAC Analogique ? | Compatibilité PoC VGA-SDR |
| :--- | :---: | :--- | :---: | :---: |
| **Radeon HD 4000 / 5000 / 6000** | 2008–2011 | TeraScale 1 & 2 | **OUI** (VGA / DVI-I natif) | ✅ **100 % Compatible** |
| **Radeon HD 7000 / HD 8000** | 2012–2013 | GCN 1.0 / TeraScale | **OUI** (VGA / DVI-I) | ✅ **100 % Compatible** |
| **Radeon R5 / R7 / R9 (200 / 300)** | 2013–2015 | GCN 1.0 à 1.2 | **OUI** (sur modèles d'entrée/milieu) | ✅ Compatible (surveiller le port) |
| **Radeon R9 290/290X, R9 390, Fury** | 2013–2015 | Hawaii / Fiji | ❌ **NON (DVI-D uniquement)** | 🚫 Incompatible |
| **Radeon RX 400 / RX 500** (RX 480, 580...) | 2016+ | Polaris | ❌ **NON (Supprimé du silicium)** | 🚫 **INCOMPATIBLE** |
| **Radeon RX Vega, RX 5000+ (RDNA)** | 2017+ | Vega / RDNA 1/2/3 | ❌ **NON** | 🚫 **INCOMPATIBLE** |

### La « Reine » de l'Occasion chez AMD : La Radeon HD 5450 / HD 6450 (5 € à 10 €)
Les parcs informatiques d'entreprises (Dell OptiPlex, HP ProDesk, Lenovo ThinkCentre) regorgent de ces cartes vendues une poignée d'euros :
* Modèles : `Radeon HD 5450`, `Radeon HD 6450`, `Radeon R5 230` (renommage récent), `Radeon HD 7470`.
* Disponibles à **5 € ou 10 €** partout en France sur LeBonCoin, Vinted ou les recycleries associatives.
* Équipées d'un RAMDAC 400 MHz double canal très stable.

---

## 4. Le « Sweet Spot » Radioamateur : Pourquoi les cartes à 10 € surpassent les GPU Gaming

Dans une station radio logicielle, une carte graphique bureautique passive d'entrée de gamme est **techniquement supérieure** à une grosse carte de jeu :

```
             CARTE GAMING (ex: GTX 960)                 CARTE BUREAUTIQUE (ex: GT 710 / HD 6450)
  ┌──────────────────────────────────────────────┐   ┌──────────────────────────────────────────────┐
  │ Consommation : 120 W (Alimentation 6 broches)│   │ Consommation : 15 W à 19 W (Alimenté PCIe)  │
  │ Refroidissement : 1 à 2 ventilateurs PWM     │   │ Refroidissement : 100 % passif (Fanless)     │
  │ Bruit : Microphonie mécanique + bruit alim   │   │ Bruit : Silence total, 0 parasite moteur     │
  │ Connectique : DVI-I (Adaptateur requis)      │   │ Connectique : Port VGA DE-15 direct soudé    │
  │ Encombrement : Double slot, 24 cm de long    │   │ Encombrement : Low-profile compact           │
  │ Prix : 25 € à 40 €                           │   │ Prix : 5 € à 15 €                            │
  └──────────────────────────────────────────────┘   └──────────────────────────────────────────────┘
```

### Justification technique :
1. **La charge GPU est minime :**  
   Notre Fragment Shader exécute un DDS 32 bits et un produit de quadrature à 2 composantes par pixel. En mode optimisé $800\times 2000$ @ 60 Hz, le débit requis n'est que de **$96\text{ MPix/s}$**. Même les 48 cœurs modestes d'une GT 610 ou les 80 processeurs de flux d'une HD 5450 n'utilisent que moins de 5 % de leur puissance de calcul pour délivrer ce flux à 60 FPS constants (**0 trame en retard**).
2. **L'absence de ventilateur préserve la pureté spectrale :**  
   Les ventilateurs asservis en modulation de largeur d'impulsion (PWM) génèrent des pointes de courant sur les rails 12 V de la carte graphique. En l'absence de découplage lourd, ces commutations parasitent les alimentations analogiques du RAMDAC. Une carte **passive (fanless)** élimine ce problème à la source.

---

## 5. Prise en Charge des Pilotes sous Linux (Nouveau vs Radeon)

L'émetteur radio fonctionne exclusivement avec les **pilotes open-source intégrés au noyau Linux**, qui autorisent la programmation directe des registres d'affichage sans verrouillage propriétaire.

### NVIDIA sous le pilote `nouveau`
* **Chargement :** Automatique avec le noyau Linux standard (pas besoin d'installer le pilote binaire propriétaire NVIDIA).
* **Nom de sortie typique :** `VGA-1` (ou `DVI-I-1`).
* **Forçage physique sysfs :**
  ```bash
  echo on | sudo tee /sys/class/drm/card0-VGA-1/status
  ```
* **Injection modeline :** Gérée nativement par `xrandr`.

### AMD sous le pilote `radeon` (Mesa Gallium `r600` / `radeonsi`)
* **Chargement :** Automatique dans le noyau pour toute la série HD 5000 / 6000 / 7000 / R5.
* **Nom de sortie typique :** `VGA-0` (ou `VGA-1`).
* **Forçage physique sysfs :**
  ```bash
  echo on | sudo tee /sys/class/drm/card0-VGA-0/status
  ```
* **Support ModernGL :** Implémente nativement OpenGL 3.3 Core Profile et OpenGL 4.1.

Notre script [`setup_display.sh`](./setup_display.sh) détecte automatiquement la première sortie analogique active quel que soit le constructeur (`VGA-1`, `VGA-0` ou `DVI-I-1`).

---

## 6. Guide d'Achat d'Occasion & Matrice Comparative

### La Checklist pour inspecter les annonces (LeBonCoin / Cash Converters / Brocantes) :
1. **La prise bleue :** Recherchez la prise trapézoïdale bleue à 15 broches (**VGA DE-15**). Si elle est présente directement sur l'équerre métallique de la carte, la compatibilité est garantie à 100 %.
2. **Si la prise est blanche (DVI) :** Vérifiez impérativement que c'est un connecteur **DVI-I** (présence des 4 trous en croix entourant la languette plate de gauche). Si la languette est seule au milieu d'un espace vide, c'est un **DVI-D numérique : fuyez !**
3. **Le dissipateur :** Privilégiez les cartes recouvertes d'un simple bloc d'ailettes en aluminium noir ou argenté sans ventilateur.

---

### Tableau Comparatif des Cartes Recommandées :

| Modèle de Carte | Constructeur | Génération | Prix d'Occasion | Sortie Vidéo | Refroidissement | TDP | Recommandation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GeForce GT 710** | NVIDIA | Kepler | 10 € – 15 € | VGA natif | **Passif** | 19 W | 🌟 **Choix N°1 NVIDIA** |
| **Radeon HD 5450** | AMD | TeraScale 2 | **5 € – 10 €** | VGA natif | **Passif** | **19 W** | 🌟 **Choix N°1 Économique** |
| **Radeon HD 6450** | AMD | TeraScale 2 | **5 € – 10 €** | VGA natif | **Passif** | **18 W** | 🌟 **Choix N°1 Économique** |
| **Radeon R5 230** | AMD | TeraScale 2 | 10 € – 15 € | VGA natif | **Passif** | 19 W | ✅ Excellent |
| **GeForce GT 610** | NVIDIA | Fermi | 5 € – 10 € | VGA natif | **Passif** | 29 W | ✅ Très bon |
| **GeForce GT 630** *(Notre PoC)*| NVIDIA | Fermi/Kepler | 10 € – 15 € | VGA natif | Actif/Passif | 49 W | ✅ Validé banc d'essai |
| **Radeon HD 7470** | AMD | TeraScale 2 | 5 € – 10 € | DVI-I / DP | Actif | 27 W | ✅ Bon (OEM Dell/HP) |
| **GeForce GTX 750 Ti** | NVIDIA | Maxwell | 20 € – 25 € | DVI-I | Actif | 60 W | ⚠️ Adaptateur DVI requis |
| **GeForce GTX 960** | NVIDIA | Maxwell | 25 € – 30 € | DVI-I | Actif | 120 W | ⚠️ Trop puissante / encombrante |
| **GeForce GTX 1060** | NVIDIA | Pascal | ~40 € | DVI-D / HDMI | Actif | 120 W | 🚫 **INCOMPATIBLE (Pas de DAC)** |
| **Radeon RX 480 / 580** | AMD | Polaris | 40 € – 60 € | DVI-D / DP | Actif | 185 W | 🚫 **INCOMPATIBLE (Pas de DAC)** |

---

## 7. Analyse Économique et Compétitivité face aux SDR Dédiés (HackRF One)

Face à un matériel SDR de laboratoire dédié, transformer une carte graphique d'occasion en émetteur HF constitue une alternative extraordinairement compétitive pour le radioamateur ou l'expérimentateur :

| Critère | HackRF One (Great Scott Gadgets / Clones) | Émetteur GPU RAMDAC (GT 710 / HD 5450) |
| :--- | :---: | :---: |
| **Coût d'acquisition matériel** | 120 € à 350 € | **5 € à 15 €** sur LeBonCoin |
| **Composants d'adaptation RF** | Aucun en test local (filtres requis en émission) | Condensateur NP0 + Atténuateur Pi (**~1 €**) |
| **Filtre de bande 20m** | Recommandé en émission | Filtre passe-bande 3 résonateurs T37-6 (**~6 €**) |
| **Budget total station d'émission** | **150 € à 380 €** | **Moins de 25 € tout compris** |
| **Résolution du convertisseur DAC** | 8 bits | **8 bits** (triple DAC vidéo) |
| **Sur-échantillonnage en HF (14 MHz)** | 2 à 20 MSPS (sur-échantillonnage faible) | **120 à 148,5 MSPS (sur-échantillonnage 8x à 10x !)** |
| **Stabilité d'horloge native** | Quartz standard (TCXO en option payante) | Quartz vidéo d'usine stable à **$\pm 2$ à $4\text{ PPM}$** |
| **Charge du processeur hôte (CPU)** | Élevée (calcul I/Q continu + flux USB lourd) | **Nulle** (synthèse RF exécutée directement sur le GPU) |
| **Puissance de sortie brute** | $\approx +10\text{ dBm}$ (10 mW) | $\approx +1\text{ dBm}$ (1,25 mW) |
| **Risque de casse matériel** | Matériel coûteux à protéger | Carte graphique sacrifiable à 10 € |

---

## 8. Synthèse Finale

Pour équiper un PC ou un serveur domestique d'un émetteur radio d'expérimentation économique :
1. **Cherchez sur LeBonCoin :** `GeForce GT 710 passive` ou `Radeon HD 5450` (budget : **10 €**).
2. **Vérifiez la présence du port bleu VGA DE-15** sur la photo.
3. Branchez la carte sur un slot PCIe libre.
4. Lancez notre suite logicielle [vga-hamradio](./README.md) sous Linux : vous disposez d'un **émetteur HF / SSTV autonome, silencieux et ultra-compétitif pour moins de 25 € composants compris**.
