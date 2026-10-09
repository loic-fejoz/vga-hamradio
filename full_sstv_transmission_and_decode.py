#!/usr/bin/env python3
"""
full_sstv_transmission_and_decode.py - Émission complète SSTV Martin 1 et décodage automatique
"""

import subprocess
import time
import sys
import os

import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Émission complète SSTV Martin 1 et décodage automatique"
    )
    parser.add_argument(
        "-s", "--rate", type=float, default=250000.0,
        help="Taux d'échantillons SDR en Sps (ex: 250000, 500000, 1000000, défaut: 250000)"
    )
    parser.add_argument(
        "-d", "--duration", type=float, default=125.0,
        help="Durée totale d'enregistrement en secondes (défaut: 125.0)"
    )
    parser.add_argument(
        "-f", "--center", type=float, default=14220000.0,
        help="Fréquence centrale SDR en Hz (défaut: 14.220 MHz)"
    )
    parser.add_argument(
        "-c", "--carrier", type=float, default=14230034.0,
        help="Fréquence exacte de la porteuse RF en Hz (défaut: 14.230034 MHz)"
    )
    parser.add_argument(
        "-g", "--gain", type=float, default=40.0,
        help="Gain IFGR SDR (défaut: 40.0 dB)"
    )
    parser.add_argument(
        "-o", "--output", default="image_recue.png",
        help="Nom du fichier image décodé (défaut: image_recue.png)"
    )
    parser.add_argument(
        "-w", "--wav", default="sstv_audio_demod.wav",
        help="Nom du fichier WAV démodulé (défaut: sstv_audio_demod.wav)"
    )
    parser.add_argument(
        "-m", "--mire", default="mire_f4jxq.png",
        help="Nom de l'image de test émise (défaut: mire_f4jxq.png)"
    )
    parser.add_argument(
        "--pclk", type=float, default=None,
        help="Pixel Clock du mode vidéo en Hz (défaut: auto-détection via xrandr)"
    )
    parser.add_argument(
        "--htotal", type=int, default=None,
        help="H_total du mode vidéo (défaut: auto-détection)"
    )
    parser.add_argument(
        "--vtotal", type=int, default=None,
        help="V_total du mode vidéo (défaut: auto-détection)"
    )
    parser.add_argument(
        "--cpp", "--use-cpp", action="store_true",
        help="Utiliser le moteur de rendu C/C++ haute cadence (vga_tx_gpu) sur my-yuno"
    )
    args = parser.parse_args()

    capture_file = "/dev/shm/sstv_full.cf32"
    duration = args.duration
    sdr_center = args.center
    sdr_rate = args.rate
    gain = args.gain

    print("="*70)
    print("🚀 ÉMISSION SSTV COMPLÈTE & DÉCODAGE AUTOMATIQUE")
    print("="*70)
    print(f"[*] Durée totale             : {duration:.1f} secondes")
    print(f"[*] Fréquence centrale SDR   : {sdr_center/1e6:.3f} MHz")
    print(f"[*] Taux d'échantillons      : {sdr_rate/1e3:.1f} kSps")
    if args.pclk is not None:
        print(f"[*] Pixel Clock forcé        : {args.pclk/1e6:.3f} MHz (H={args.htotal}, V={args.vtotal})")
    else:
        print("[*] Pixel Clock GPU          : Auto-détection dynamique sur my-yuno")
    print(f"[*] Moteur GPU distant       : {'C/C++ Déterministe (vga_tx_gpu)' if args.cpp else 'Python Natif (moderngl)'}")
    print(f"[*] Fichier de capture       : {capture_file}")
    print("="*70)

    # 1. Démarrer la capture SDR
    print(f"\n[1/3] Démarrage de l'enregistrement SDRplay ({args.duration} secondes)...")
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

    # 2. Déclencher l'émission SSTV sur my-yuno
    print(f"[2/3] Lancement de l'émission SSTV Martin 1 sur my-yuno ({args.mire}) pour {duration:.1f}s...")
    tx_cmd = f"cd ~/projets/vga-hamradio && DISPLAY=:0 .venv/bin/python3 vga_sstv.py {args.mire} -f 14.230e6 --duration {duration}"
    if args.pclk is not None:
        tx_cmd += f" --pclk {args.pclk} --htotal {args.htotal} --vtotal {args.vtotal}"
    if args.cpp:
        tx_cmd += " --cpp"
    cmd_ssh = ["ssh", "192.168.1.26", tx_cmd]
    tx_proc = subprocess.Popen(cmd_ssh, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    print("[*] Émission en cours... Attente des 120 secondes d'acquisition...")

    # Attente fin capture
    cap_proc.wait()
    print("[+] Enregistrement SDR terminé !")

    # Attente fin émetteur
    tx_proc.wait()
    print("[+] Émetteur GPU terminé !")

    # 3. DÉCODAGE
    print("\n[3/3] Décodage numérique de l'image SSTV...")
    from decode_martin1 import decode_sstv_from_iq
    decode_sstv_from_iq(
        iq_filename=capture_file,
        sdr_center_freq=sdr_center,
        sdr_rate=sdr_rate,
        carrier_freq=args.carrier,
        output_image=args.output,
        output_wav=args.wav,
        reference_image=args.mire
    )

if __name__ == '__main__':
    main()
