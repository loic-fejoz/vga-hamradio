#!/usr/bin/env bash
# ==============================================================================
# setup_display.sh - Configuration et activation réelle du CRTC VGA pour émission SDR
# ==============================================================================

set -e

MODE="1024"
CUSTOM_OUTPUT=""

while getopts "o:r:m:h" opt; do
    case "$opt" in
        o) CUSTOM_OUTPUT="$OPTARG" ;;
        r) MODE="$OPTARG" ;;
        m) MODE="$OPTARG" ;;
        h)
            echo "Usage: $0 [-o OUTPUT] [-m 1024|60|120]"
            echo "  -o OUTPUT : Spécifier la sortie (ex: VGA-1 ou DVI-I-1)"
            echo "  -m MODE   : Mode vidéo (1024=Mode A qHD 148MHz f_H=125k [défaut], 60=1080p@60Hz, 120=1080p@120Hz)"
            exit 0
            ;;
        *) exit 1 ;;
    esac
done

echo "========================================================================"
echo "🔧 CONFIGURATION DE LA SORTIE VIDÉO VGA (NVIDIA / NOUVEAU / X11)"
echo "========================================================================"

if ! command -v xrandr &> /dev/null; then
    echo "[-] Erreur : 'xrandr' n'est pas installé ou aucun serveur X11 n'est détecté."
    exit 1
fi

# 1. Sélection de la sortie vidéo
if [ -n "$CUSTOM_OUTPUT" ]; then
    VGA_OUTPUT="$CUSTOM_OUTPUT"
else
    # Préférer VGA-1 si présent, sinon DVI-I-1
    if xrandr | grep -q "^VGA-1 "; then
        VGA_OUTPUT="VGA-1"
    elif xrandr | grep -q "^DVI-I-1 "; then
        VGA_OUTPUT="DVI-I-1"
    else
        VGA_OUTPUT=$(xrandr | grep -Ei "VGA|DVI-I|CRT" | awk '{print $1}' | head -n 1)
    fi
fi

if [ -z "$VGA_OUTPUT" ]; then
    echo "[-] Erreur : Aucune sortie analogique (VGA / DVI-I) trouvée dans xrandr."
    exit 1
fi

echo "[*] Sortie analogique ciblée : $VGA_OUTPUT"

# 2. Vérification de l'état du connecteur dans sysfs
SYSFS_STATUS_FILE=$(ls /sys/class/drm/card*-${VGA_OUTPUT}/status 2>/dev/null | head -n 1 || true)
if [ -n "$SYSFS_STATUS_FILE" ]; then
    CURRENT_STATUS=$(cat "$SYSFS_STATUS_FILE" 2>/dev/null || echo "unknown")
    echo "[*] Statut physique du connecteur ($SYSFS_STATUS_FILE) : $CURRENT_STATUS"
    
    if [ "$CURRENT_STATUS" != "connected" ]; then
        echo "[!] Le connecteur est vu comme 'disconnected' par le noyau."
        echo "    Tentative d'activation forcée via sysfs si possible..."
        if [ -w "$SYSFS_STATUS_FILE" ]; then
            echo on > "$SYSFS_STATUS_FILE" 2>/dev/null || true
            echo "[+] Statut forcé à 'on' dans sysfs."
        else
            echo "    (Astuce : Si le CRTC refuse de démarrer, branchez votre charge 50Ω ou exécutez :"
            echo "     echo on | sudo tee $SYSFS_STATUS_FILE )"
        fi
    fi
fi

if [ "$MODE" = "120" ] || [ "$MODE" = "119" ] || [ "$MODE" = "118.87" ] || [ "$MODE" = "1080_120" ]; then
    MODE_NAME="1920x1080_118.87"
    WIDTH="1920"
    HEIGHT="1080"
    PCLK="282.85"
    HTOTAL="2080"
    VTOTAL="1144"
    echo "[+] Configuration du mode 1080p @ 118.87Hz CVT-RB (Pixel Clock : 282.85 MHz)..."
    xrandr --newmode "$MODE_NAME" 282.85 1920 1968 2000 2080 1080 1083 1088 1144 +hsync -vsync 2>/dev/null || true
elif [ "$MODE" = "60" ] || [ "$MODE" = "1080_60" ]; then
    MODE_NAME="1920x1080_60.00"
    WIDTH="1920"
    HEIGHT="1080"
    PCLK="148.50"
    HTOTAL="2200"
    VTOTAL="1125"
    echo "[+] Configuration du mode 1080p @ 60Hz standard (Pixel Clock : 148.50 MHz)..."
    xrandr --newmode "$MODE_NAME" 148.50 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync 2>/dev/null || true
elif [ "$MODE" = "800" ] || [ "$MODE" = "800x600" ] || [ "$MODE" = "mode_c" ] || [ "$MODE" = "125" ] || [ "$MODE" = "125k" ]; then
    MODE_NAME="800x2000_125k"
    WIDTH="800"
    HEIGHT="2000"
    PCLK="120.00"
    HTOTAL="960"
    VTOTAL="2083"
    echo "[+] Configuration du Mode C Hors-Bande (800x2000 @ 120.00 MHz, f_H = 125.0 kHz, f_V = 60.0 Hz, harmoniques hors bande 20m)..."
    xrandr --newmode "$MODE_NAME" 120.00 800 824 856 960 2000 2003 2008 2083 +hsync -vsync 2>/dev/null || true
else
    MODE_NAME="1024x2000_125k"
    WIDTH="1024"
    HEIGHT="2000"
    PCLK="148.00"
    HTOTAL="1184"
    VTOTAL="2083"
    echo "[+] Configuration du Mode A Hors-Bande (1024x2000 @ 148.00 MHz, f_H = 125.0 kHz, f_V = 60.0 Hz, harmoniques hors bande 20m)..."
    xrandr --newmode "$MODE_NAME" 148.00 1024 1072 1104 1184 2000 2003 2008 2083 +hsync -vsync 2>/dev/null || true
fi

xrandr --addmode "$VGA_OUTPUT" "$MODE_NAME" 2>/dev/null || true

# 4. Activation du framebuffer et du CRTC
echo "[+] Application de la résolution $MODE_NAME et allocation du CRTC..."
xrandr --fb ${WIDTH}x${HEIGHT} --output "$VGA_OUTPUT" --mode "$MODE_NAME" --crtc 0 2>/dev/null || \
xrandr --output "$VGA_OUTPUT" --mode "$MODE_NAME" 2>/dev/null || true

# 5. VÉRIFICATION RÉELLE DE L'ACTIVATION DU CRTC
IS_ACTIVE=0
ACTIVE_INFO=$(xrandr --verbose | grep -A 8 "^$VGA_OUTPUT" | grep -E "CRTC:.*[0-9]+" || true)
if [ -n "$ACTIVE_INFO" ]; then
    IS_ACTIVE=1
fi

echo ""
if [ "$IS_ACTIVE" -eq 1 ]; then
    echo "========================================================================"
    echo "✅ CRTC ACTIF : LE RAMDAC GÉNÈRE DU SIGNAL SUR $VGA_OUTPUT"
    echo "========================================================================"
    echo "   Sortie vidéo       : $VGA_OUTPUT"
    echo "   Mode actif         : $MODE_NAME ($PCLK MHz)"
    echo "   Contrôleur         : $ACTIVE_INFO"
    
    # Configuration Gamma 1.0 (linéarité stricte)
    xrandr --output "$VGA_OUTPUT" --gamma 1.0:1.0:1.0 2>/dev/null || true
    xset s off 2>/dev/null || true
    xset -dpms 2>/dev/null || true
    echo "   Correction Gamma   : 1.0 (Linéaire / Pas de distorsion)"
    echo "   Gestion d'énergie  : DPMS désactivé"
    echo "========================================================================"
    echo "Paramètres pour vga_sstv.py :"
    echo "   --pclk ${PCLK}e6 --htotal $HTOTAL --vtotal $VTOTAL"
    echo "========================================================================"
    exit 0
else
    echo "========================================================================"
    echo "⚠️  ATTENTION : LE CRTC N'EST PAS ENCORE ACTIF SUR $VGA_OUTPUT"
    echo "========================================================================"
    echo "Le pilote Nouveau / X11 attend qu'un signal ou une impédance soit détecté."
    echo ""
    echo "Pour débloquer l'activation :"
    echo "1. Branchez votre charge 50Ω (âme sur broche 1, blindage sur broche 6)."
    echo "   Si possible, mettez aussi une charge de 50 à 75Ω sur Vert (broche 2) et Bleu (broche 3)."
    echo "2. Ou forcez le statut du connecteur dans le noyau :"
    if [ -n "$SYSFS_STATUS_FILE" ]; then
        echo "   echo on | sudo tee $SYSFS_STATUS_FILE"
    else
        echo "   echo on | sudo tee /sys/class/drm/card0-${VGA_OUTPUT}/status"
    fi
    echo "3. Relancez ensuite ce script :"
    echo "   ./setup_display.sh -o $VGA_OUTPUT -r $REFRESH_RATE"
    echo "========================================================================"
    exit 1
fi
