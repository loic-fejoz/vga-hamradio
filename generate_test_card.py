#!/usr/bin/env python3
"""
generate_test_card.py - Générateur de mire d'essai SSTV paramétrable
Auteur: F4JXQ / PoC GPU SDR
"""

import os
import re
import argparse
from PIL import Image, ImageDraw, ImageFont

def guess_ham_band(freq_mhz):
    """Devine la bande radioamateur à partir de la fréquence en MHz."""
    if 1.8 <= freq_mhz <= 2.0:
        return "BANDE 160M"
    elif 3.5 <= freq_mhz <= 3.8:
        return "BANDE 80M"
    elif 5.35 <= freq_mhz <= 5.37:
        return "BANDE 60M"
    elif 7.0 <= freq_mhz <= 7.3:
        return "BANDE 40M"
    elif 10.1 <= freq_mhz <= 10.15:
        return "BANDE 30M"
    elif 14.0 <= freq_mhz <= 14.35:
        return "BANDE 20M"
    elif 18.068 <= freq_mhz <= 18.168:
        return "BANDE 17M"
    elif 21.0 <= freq_mhz <= 21.45:
        return "BANDE 15M"
    elif 24.89 <= freq_mhz <= 24.99:
        return "BANDE 12M"
    elif 28.0 <= freq_mhz <= 29.7:
        return "BANDE 10M"
    elif 50.0 <= freq_mhz <= 54.0:
        return "BANDE 6M"
    elif 70.0 <= freq_mhz <= 70.5:
        return "BANDE 4M"
    elif 144.0 <= freq_mhz <= 148.0:
        return "BANDE 2M"
    elif 430.0 <= freq_mhz <= 440.0:
        return "BANDE 70CM"
    return None

def parse_frequency(freq_input):
    """Normalise l'entrée de fréquence en chaîne lisible et en valeur numérique MHz."""
    if not freq_input:
        return "14.230 MHz", 14.230

    # Nettoyage chaîne
    s = str(freq_input).strip().upper()
    s = s.replace("MHZ", "").replace("HZ", "").strip()

    try:
        val = float(s)
        # Si la valeur est en Hz (ex: 14230000 ou 14.230e6)
        if val >= 100000:
            val_mhz = val / 1e6
        # Si la valeur est en kHz (ex: 14230)
        elif val >= 1000:
            val_mhz = val / 1e3
        else:
            val_mhz = val
        return f"{val_mhz:.3f} MHz", val_mhz
    except ValueError:
        # Chaîne personnalisée telle quelle
        return str(freq_input).strip(), None

def generate_sstv_test_card(callsign="F4JXQ", freq="14.230 MHz", band=None,
                            mode="USB", subtitle="SSTV GPU TX - GEFORCE GT 630",
                            output_path=None):
    """
    Génère une mire d'essai SSTV haute visibilité au format natif Martin 1 (320x256).
    """
    callsign = callsign.strip().upper()
    callsign_safe = re.sub(r'[^A-Z0-9]', '_', callsign).lower()

    if output_path is None:
        output_path = f"mire_{callsign_safe}.png"

    # Normalisation fréquence et bande
    freq_str, freq_mhz = parse_frequency(freq)
    if band:
        band_str = band.strip().upper()
        if not band_str.startswith("BANDE") and not band_str.startswith("BAND"):
            band_str = f"BANDE {band_str}"
    elif freq_mhz:
        band_str = guess_ham_band(freq_mhz)
    else:
        band_str = None

    # Ligne d'info radio
    mode_str = f" {mode.strip().upper()}" if mode else ""
    if band_str:
        info_text = f"{freq_str}{mode_str} ({band_str})"
    else:
        info_text = f"{freq_str}{mode_str}"

    # Résolution NATIVE Martin 1 : 320x256 (aucun flou de redimensionnement)
    width, height = 320, 256
    img = Image.new("RGB", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --------------------------------------------------------------------------
    # 1. Barre de couleurs EBU / SMPTE (Haut : y = 0 .. 95)
    # --------------------------------------------------------------------------
    colors = [
        (255, 255, 255), # Blanc
        (255, 255,   0), # Jaune
        (  0, 255, 255), # Cyan
        (  0, 255,   0), # Vert
        (255,   0, 255), # Magenta
        (255,   0,   0), # Rouge
        (  0,   0, 255), # Bleu
        (  0,   0,   0)  # Noir
    ]
    
    bar_w = width // len(colors) # 40 px par barre
    bar_h = 95
    for i, color in enumerate(colors):
        x0 = i * bar_w
        x1 = (i + 1) * bar_w if i < len(colors) - 1 else width
        draw.rectangle([x0, 0, x1, bar_h], fill=color)

    # --------------------------------------------------------------------------
    # 2. Dégradé de gris (y = 95 .. 130)
    # --------------------------------------------------------------------------
    num_steps = 10
    step_w = width // num_steps # 32 px par marche
    for i in range(num_steps):
        val = int(i * 255 / (num_steps - 1))
        x0 = i * step_w
        x1 = (i + 1) * step_w if i < num_steps - 1 else width
        draw.rectangle([x0, 95, x1, 130], fill=(val, val, val))

    # --------------------------------------------------------------------------
    # 3. Zone d'identification Radioamateur (y = 130 .. 256, Fond Noir Profond)
    # --------------------------------------------------------------------------
    draw.rectangle([0, 130, width, height], fill=(0, 0, 0))

    # Chargement polices TrueType avec adaptation dynamique selon la longueur de l'indicatif
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    call_font_size = 44
    call_text = f"DE {callsign}"

    # Réduction automatique de la police si l'indicatif est long (ex: avec /P ou indicatif étranger)
    while call_font_size >= 24:
        try:
            test_font = ImageFont.truetype(font_path, call_font_size)
        except IOError:
            test_font = ImageFont.load_default()
            break
        bbox = draw.textbbox((0, 0), call_text, font=test_font)
        if bbox[2] - bbox[0] <= width - 20:
            break
        call_font_size -= 2

    try:
        font_call = ImageFont.truetype(font_path, call_font_size)
        font_sub  = ImageFont.truetype(font_path, 16)
        font_info = ImageFont.truetype(font_path, 13)
    except IOError:
        font_call = font_sub = font_info = ImageFont.load_default()

    # Indicatif - Très contrasté et centré (Jaune vif sur Noir)
    bbox_call = draw.textbbox((0, 0), call_text, font=font_call)
    w_call = bbox_call[2] - bbox_call[0]
    h_call = bbox_call[3] - bbox_call[1]
    x_call = (width - w_call) // 2
    y_call = 136 + (44 - call_font_size) // 2

    # Tracé gras renforcé (halo 1px pour épaisseur maximale en radio analogique)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            draw.text((x_call + dx, y_call + dy), call_text, font=font_call, fill=(255, 230, 0))

    # Sous-titre : Émetteur matériel / GPU (Blanc éclatant)
    if subtitle:
        bbox_sub = draw.textbbox((0, 0), subtitle, font=font_sub)
        w_sub = bbox_sub[2] - bbox_sub[0]
        draw.text(((width - w_sub) // 2, 196), subtitle, font=font_sub, fill=(255, 255, 255))

    # Bande & Fréquence (Cyan éclatant)
    bbox_info = draw.textbbox((0, 0), info_text, font=font_info)
    w_info = bbox_info[2] - bbox_info[0]
    draw.text(((width - w_info) // 2, 226), info_text, font=font_info, fill=(0, 255, 255))

    # Bordure blanche 2px
    draw.rectangle([0, 0, width - 1, height - 1], outline=(255, 255, 255), width=2)

    img.save(output_path)
    print(f"[+] Mire d'essai SSTV native 320x256 générée avec succès : {output_path}")
    print(f"    - Indicatif : {callsign}")
    print(f"    - Fréquence : {freq_str} ({mode})")
    if band_str:
        print(f"    - Bande     : {band_str}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Générateur de mire d'essai SSTV Martin 1 (320x256) personnalisée pour Radioamateur"
    )
    parser.add_argument("callsign", nargs="?", default="F4JXQ",
                        help="Indicatif Radioamateur (ex: F4JXQ, ON4ABC, W1AW) [Défaut: F4JXQ]")
    parser.add_argument("-f", "--freq", default="14.230 MHz",
                        help="Fréquence d'émission (ex: 14.230, 14.230 MHz, 7.171, 144.500) [Défaut: 14.230 MHz]")
    parser.add_argument("-b", "--band", default=None,
                        help="Bande radioamateur (ex: 20M, 40M, 2M) [Auto-détectée si omise]")
    parser.add_argument("-m", "--mode", default="USB",
                        help="Mode de modulation (ex: USB, FM, LSB) [Défaut: USB]")
    parser.add_argument("-s", "--sub", "--subtitle", dest="subtitle",
                        default="SSTV GPU TX - GEFORCE GT 630",
                        help="Sous-titre matériel [Défaut: SSTV GPU TX - GEFORCE GT 630]")
    parser.add_argument("-o", "--out", "--output", dest="output", default=None,
                        help="Nom de fichier de sortie [Défaut: mire_<callsign>.png]")

    args = parser.parse_args()

    generate_sstv_test_card(
        callsign=args.callsign,
        freq=args.freq,
        band=args.band,
        mode=args.mode,
        subtitle=args.subtitle,
        output_path=args.output
    )
