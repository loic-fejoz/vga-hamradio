Voici le compte-rendu technique de notre séance de conception. Vous pouvez le soumettre directement à votre assistant de code (ou à un LLM spécialisé en développement) pour générer l'application complète.
------------------------------
## 📝 Compte-Rendu Technique : Émetteur Radio 2FSK / FHSS via GPU (Détournement DAC VGA)## 📌 Objectif du Projet
Concevoir une Preuve de Concept (PoC) sous Linux (octobre 2026) permettant de transformer une vieille carte graphique analogique (GeForce GT 610 avec RAMDAC à 400 MHz) en un émetteur radio logicielle (SDR) en bande VHF (6 mètres / 50 MHz). L'objectif est d'implémenter une modulation 2FSK stable, sans latence ni gigue (jitter) induite par l'OS, en déléguant 100 % du calcul et du timing aux cœurs de calcul du GPU via un Shader GLSL.
------------------------------
## 🛠️ Architecture de la Solution (Zéro CPU / Zéro Jitter)
Plutôt que d'écrire bit par bit dans le Framebuffer Linux (ce qui introduit de la gigue système), l'architecture repose sur deux piliers :

   1. La Texture de Données (Tampon RF) : Le message complet à transmettre est converti en une suite de bits (0 ou 1) et envoyé une seule fois au GPU sous la forme d'une texture 1D (Noir/Blanc).
   2. Le Fragment Shader Autonome : Le GPU utilise son horloge matérielle interne haute précision (u_time) et le taux de transmission souhaité (u_baudrate) pour lire de façon déterministe le bon bit dans la texture et calculer la sinusoïde RF pixel par pixel.

## Spécifications RF cibles (Bande des 6m)

* Mode vidéo requis : 1920x1080 @ 60Hz → Pixel Clock ($f_{clk}$) = 148,5 MHz
* Fréquence Espace (Ton 0) : 50,100 MHz
* Fréquence Marque (Ton 1) : 50,120 MHz (Shift standard de 20 kHz)
* Sortie physique : Broche 1 (Rouge) du connecteur VGA (signal analogique quantifié sur 8 bits, 0V à 0.7V).

------------------------------
## 💻 Spécifications du Code pour l'Assistant de Code## 1. Le Fragment Shader (GLSL 330)
Ce code calcule l'intensité du canal Rouge pour chaque pixel horizontal (gl_FragCoord.x), modulant le signal à 50 MHz par synthèse numérique directe (DDS) logicielle.

#version 330 coreout vec4 FragColor;
// Variables d'entrée fournies par le CPUuniform sampler1D u_data_texture; // Message sous forme de texture 1D (1px = 1bit)uniform float u_baudrate;         // Vitesse (ex: 1200.0)uniform int u_texture_size;       // Nombre total de bitsuniform float u_time;             // Temps matériel fourni par le GPU
// Constantes RF calculées pour la bande des 6mconst float F_CLK = 148500000.0;   // 148.5 MHzconst float F0 = 50100000.0;       // 50.100 MHz (Ton 0)const float F1 = 50120000.0;       // 50.120 MHz (Ton 1)const float PI = 3.14159265359;
void main() {
    // 1. Déterminer l'index du bit à émettre selon le temps absolu
    float bit_index = floor(u_time * u_baudrate);
    
    // Silence radio si le message est entièrement transmis
    if (bit_index >= u_texture_size) {
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    
    // 2. Lecture stéganographique du bit dans la texture 1D
    float tex_coord = (bit_index + 0.5) / float(u_texture_size);
    vec4 data_pixel = texture(u_data_texture, tex_coord);
    bool bit_est_un = (data_pixel.r > 0.5);
    
    // 3. Sélection de la fréquence FSK
    float freq = bit_est_un ? F1 : F0;
    
    // 4. Synthèse de l'onde sinusoïdale sur l'axe X (0 à 1919)
    float x = gl_FragCoord.x;
    float onde = 0.5 + 0.5 * sin(2.0 * PI * x * (freq / F_CLK));
    
    // Sortie analogique sur le DAC Rouge (Vert/Bleu à 0)
    FragColor = vec4(onde, 0.0, 0.0, 1.0);
}

## 2. Le Script de Pilotage (Python avec ModernGL)
Demandez à votre assistant de coder ce script selon le squelette suivant :

* Pré-requis : pip install FreeGLUT ModernGL numpy
* Fonctionnalités attendues :
1. Initialiser un contexte OpenGL en mode "sans fenêtre" (headless).
   2. Prendre une chaîne de caractères (ex: "CQ DE [INDICATIF]"), la convertir en un tableau binaire (0 et 1), puis générer une texture 1D ModernGL (format R8 ou RGB8).
   3. Compiler le shader ci-dessus et mapper un rectangle qui couvre l'intégralité de l'écran virtuel (Render-to-FrameBuffer).
   4. Lancer une boucle de rendu qui rafraîchit la variable u_time à chaque itération à l'aide de time.perf_counter() et appelle le rendu du shader.

------------------------------
## 🔌 Raccordement et Validation Radioamateur

   1. Câblage : Sectionner un câble VGA. Souder l'âme d'un câble coaxial RG58 sur la Broche 1 (Rouge) et le blindage sur la Broche 6 (Masse Rouge).
   2. Sécurité Matérielle : Interdiction d'émettre directement sur une antenne. Brancher impérativement la sortie VGA sur une charge fictive (Dummy Load) 50 Ohms ou insérer un atténuateur de puissance (ex: -30 dB) avant d'attaquer l'analyseur de spectre ou la clé SDR de contrôle.
   3. Pureté Spectrale : Le signal étant généré sous forme de sinusoïde pure quantifiée, les harmoniques sont faibles. Toutefois, le passage à la ligne (Blanking horizontal) à ~67.5 kHz créera des raies parasites autour des 50.1 MHz. Un filtre passe-bas de type Chebyshev (Coupure à 60 MHz) est indispensable en sortie de carte.

------------------------------
Pour générer le script Python exact, indiquez à votre assistant de code si vous préférez :

* Travailler en mode plein écran direct sur le Framebuffer Linux (/dev/fb0)
* Ou utiliser une fenêtre masquée ModernGL (X11/Wayland actif)

Je reste disponible si vous rencontrez une anomalie sur les formules d'incrément de phase lors des premiers essais au scope !
