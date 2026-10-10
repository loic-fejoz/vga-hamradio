#!/usr/bin/env python3
"""
full_sstv_transmission_and_decode.py - Émission complète SSTV Martin 1 et décodage automatique
"""

import subprocess
import time
import sys
import os
import struct
import argparse


def read_texture_duration(filepath):
    """Lit la durée totale et le nombre d'échantillons depuis l'en-tête d'un fichier .sstvtex."""
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "rb") as f:
            hdr = f.read(72)
            if len(hdr) < 72:
                return None
            magic, version, audio_fs, total_samples, tex_w, tex_h, total_duration, data_bytes, _ = struct.unpack(
                "<8sIIIIIdI32s", hdr
            )
            if magic == b"VGASSTV1":
                return float(total_duration)
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Émission complète SSTV Martin 1 et décodage automatique"
    )
    # Paramètres de transmission (identiques à vga_sstv.py)
    parser.add_argument(
        "image", nargs="?", default=None,
        help="Chemin vers l'image source (ex: mire_f4jxq.png)"
    )
    parser.add_argument(
        "--load-texture", "--input-texture", default=None,
        help="Charge une texture I/Q pré-enregistrée (.sstvtex) au lieu d'une image"
    )
    parser.add_argument(
        "-f", "--freq", type=float, default=14.230e6,
        help="Fréquence porteuse RF en Hz (Défaut: 14.230 MHz)"
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=None,
        help="Durée totale d'enregistrement en secondes (Défaut: automatique selon la texture ou 125.0s pour SSTV)"
    )
    parser.add_argument(
        "--pclk", type=float, default=None,
        help="Pixel Clock du mode vidéo en Hz (Défaut: auto-détection via xrandr)"
    )
    parser.add_argument(
        "--width", type=int, default=None,
        help="Largeur active (Défaut: auto-détectée)"
    )
    parser.add_argument(
        "--height", type=int, default=None,
        help="Hauteur active (Défaut: auto-détectée)"
    )
    parser.add_argument(
        "--htotal", type=int, default=None,
        help="H_total du mode vidéo (Défaut: auto-détection)"
    )
    parser.add_argument(
        "--vtotal", type=int, default=None,
        help="V_total du mode vidéo (Défaut: auto-détection)"
    )
    parser.add_argument(
        "--fullscreen", action="store_true",
        help="Plein écran sur la sortie sélectionnée"
    )
    parser.add_argument(
        "--monitor", type=int, default=0,
        help="Index du moniteur pour le plein écran"
    )
    parser.add_argument(
        "--cpp", "--use-cpp", action="store_true",
        help="Utiliser le moteur de rendu C/C++ haute cadence (vga_tx_gpu) sur my-yuno"
    )
    parser.add_argument(
        "-r", "--realtime", action="store_true",
        help="Active la priorité temps réel SCHED_FIFO (avec le moteur C/C++)"
    )

    # Paramètres de réception SDR & Décodage
    parser.add_argument(
        "-s", "--rate", type=float, default=250000.0,
        help="Taux d'échantillons SDR en Sps (Défaut: 250000)"
    )
    parser.add_argument(
        "--center", type=float, default=14.220e6,
        help="Fréquence centrale SDR en Hz (Défaut: 14.220 MHz)"
    )
    parser.add_argument(
        "-c", "--carrier", type=float, default=None,
        help="Fréquence exacte de la porteuse RF pour le décodeur en Hz (Défaut: alignée sur --freq ou 14.230034 MHz)"
    )
    parser.add_argument(
        "-g", "--gain", type=float, default=40.0,
        help="Gain IFGR SDR (Défaut: 40.0 dB)"
    )
    parser.add_argument(
        "-o", "--output", default="image_recue.png",
        help="Nom du fichier image décodé (Défaut: image_recue.png)"
    )
    parser.add_argument(
        "-w", "--wav", default="sstv_audio_demod.wav",
        help="Nom du fichier WAV démodulé (Défaut: sstv_audio_demod.wav)"
    )
    parser.add_argument(
        "-m", "--mire", default=None,
        help="Alias rétro-compatible pour l'image ou la texture de test"
    )

    args = parser.parse_args()

    # Résolution de la source d'émission (image ou texture)
    load_texture = args.load_texture
    image_src = args.image

    # Si -m / --mire a été utilisé
    if args.mire:
        if args.mire.endswith(".sstvtex"):
            load_texture = args.mire
        else:
            image_src = args.mire

    # Si l'argument positionnel est un fichier texture
    if image_src and image_src.endswith(".sstvtex"):
        load_texture = image_src
        image_src = None

    if not load_texture and not image_src:
        image_src = "mire_f4jxq.png"

    # Détermination de la durée d'enregistrement
    duration = args.duration
    if duration is None:
        if load_texture:
            tex_dur = read_texture_duration(load_texture)
            if tex_dur:
                duration = round(tex_dur + 6.0, 1)  # marge de sécurité de 6s
                print(f"[*] Durée détectée depuis '{load_texture}' : {tex_dur:.2f} s (+6s marge -> {duration} s)")
            else:
                duration = 125.0
        else:
            duration = 125.0

    sdr_center = args.center
    sdr_rate = args.rate
    gain = args.gain
    carrier_freq = args.carrier if args.carrier is not None else args.freq
    capture_file = "/dev/shm/sstv_full.cf32"

    print("=" * 70)
    print("🚀 ÉMISSION SSTV COMPLÈTE & DÉCODAGE AUTOMATIQUE")
    print("=" * 70)
    if load_texture:
        print(f"[*] Source d'émission        : Texture I/Q ({load_texture})")
    else:
        print(f"[*] Source d'émission        : Image ({image_src})")
    print(f"[*] Durée totale d'écoute    : {duration:.1f} secondes")
    print(f"[*] Fréquence centrale SDR   : {sdr_center / 1e6:.3f} MHz")
    print(f"[*] Fréquence porteuse RF    : {args.freq / 1e6:.6f} MHz")
    print(f"[*] Taux d'échantillons      : {sdr_rate / 1e3:.1f} kSps")
    if args.pclk is not None:
        print(f"[*] Pixel Clock forcé        : {args.pclk / 1e6:.3f} MHz (H={args.htotal}, V={args.vtotal})")
    else:
        print("[*] Pixel Clock GPU          : Auto-détection dynamique sur my-yuno")
    print(f"[*] Moteur GPU distant       : {'C/C++ Déterministe (vga_tx_gpu)' if args.cpp else 'Python Natif (moderngl)'}")
    print(f"[*] Fichier de capture       : {capture_file}")
    print("=" * 70)

    # 1. Démarrer la capture SDR
    print(f"\n[1/3] Démarrage de l'enregistrement SDRplay ({duration} secondes)...")
    cap_proc = subprocess.Popen([
        "./capture_iq",
        "-f", str(int(sdr_center)),
        "-s", str(int(sdr_rate)),
        "-I", str(gain),
        "-R", "0",
        "-d", str(duration),
        "-o", capture_file
    ])

    time.sleep(2.0)

    # 2. Construction de la commande distante vga_sstv.py
    tx_parts = ["cd ~/projets/vga-hamradio && DISPLAY=:0 .venv/bin/python3 vga_sstv.py"]
    if load_texture:
        tx_parts.append(f"--load-texture {load_texture}")
    else:
        tx_parts.append(f"{image_src}")

    tx_parts.append(f"-f {args.freq}")
    tx_parts.append(f"-d {duration}")

    if args.pclk is not None:
        tx_parts.append(f"--pclk {args.pclk}")
    if args.htotal is not None:
        tx_parts.append(f"--htotal {args.htotal}")
    if args.vtotal is not None:
        tx_parts.append(f"--vtotal {args.vtotal}")
    if args.width is not None:
        tx_parts.append(f"--width {args.width}")
    if args.height is not None:
        tx_parts.append(f"--height {args.height}")
    if args.fullscreen:
        tx_parts.append("--fullscreen")
    if args.monitor != 0:
        tx_parts.append(f"--monitor {args.monitor}")
    if args.cpp:
        tx_parts.append("--cpp")
    if args.realtime:
        tx_parts.append("-r")

    tx_cmd = " ".join(tx_parts)
    print(f"[2/3] Lancement de l'émission sur my-yuno pour {duration:.1f}s...")
    cmd_ssh = ["ssh", "192.168.1.26", tx_cmd]
    tx_proc = subprocess.Popen(cmd_ssh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    print(f"[*] Émission en cours... Attente des {duration:.1f} secondes d'acquisition...")

    # Attente fin capture
    cap_proc.wait()
    print("[+] Enregistrement SDR terminé !")

    # Attente fin émetteur
    tx_proc.wait()
    print("[+] Émetteur GPU terminé !")

    # 3. DÉCODAGE
    print("\n[3/3] Décodage numérique de l'image SSTV...")
    from decode_martin1 import decode_sstv_from_iq
    ref_for_decoder = image_src if image_src else "mire_f4jxq.png"
    decode_sstv_from_iq(
        iq_filename=capture_file,
        sdr_center_freq=sdr_center,
        sdr_rate=sdr_rate,
        carrier_freq=carrier_freq,
        output_image=args.output,
        output_wav=args.wav,
        reference_image=ref_for_decoder
    )


if __name__ == '__main__':
    main()
