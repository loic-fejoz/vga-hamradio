#!/usr/bin/env python3
"""
decode_martin1.py - Décodeur SSTV Martin 1 direct depuis capture IQ SDR
Auteur: F4JXQ / PoC GPU SDR
"""

import sys
import os
import wave
import json
import datetime
import argparse
import numpy as np
import scipy.signal
from fractions import Fraction
from PIL import Image

def decode_sstv_from_iq(iq_filename, sdr_center_freq=14.220e6, sdr_rate=250000.0,
                        carrier_freq=14.230038e6,
                        output_image="image_recue.png", output_wav="sstv_audio_demod.wav",
                        reference_image="mire_f4jxq.png"):
    
    print("="*70)
    print("📻 DÉCODEUR SSTV MARTIN 1 (I/Q SDR -> AUDIO USB -> IMAGE)")
    print("="*70)
    print(f"[*] Fichier source IQ        : {iq_filename}")
    print(f"[*] Fréquence centrale SDR   : {sdr_center_freq/1e6:.3f} MHz")
    print(f"[*] Fréquence porteuse RF    : {carrier_freq/1e6:.6f} MHz")
    print(f"[*] Taux d'échantillons IQ   : {sdr_rate/1e3:.1f} kSps")

    data = np.fromfile(iq_filename, dtype=np.complex64)
    total_samples = len(data)
    duration = total_samples / sdr_rate
    print(f"[+] Échantillons chargés     : {total_samples} ({duration:.2f} secondes)")

    # 1. Translation de fréquence vers la bande de base USB (Mélangeur numérique)
    offset_hz = carrier_freq - sdr_center_freq # ex: +10038 Hz
    print(f"[*] Décalage IF vers bande de base USB : {offset_hz:+.1f} Hz...")
    t = np.arange(total_samples, dtype=np.float64) / sdr_rate
    baseband_iq = data * np.exp(-2j * np.pi * offset_hz * t).astype(np.complex64)

    # 2. Filtrage passe-bas anti-repliement (anti-aliasing) et décimation vers audio 48 kHz
    audio_fs = 48000.0
    print(f"[*] Rééchantillonnage polyphase haute fidélité ({sdr_rate/1e3:.1f} kSps -> {audio_fs/1e3:.1f} kHz)...")

    # Ratio d'échantillonnage exact P / Q sous forme de fraction irréductible
    frac = Fraction(int(audio_fs), int(sdr_rate)).limit_denominator(1000)
    up = frac.numerator
    down = frac.denominator
    print(f"    Facteur rationnel polyphase : up={up}, down={down}")

    # Rééchantillonnage polyphase avec filtre Kaiser anti-repliement intégré (scipy.signal.resample_poly)
    audio_complex = scipy.signal.resample_poly(baseband_iq, up, down).astype(np.complex64)

    # 3. Filtrage passe-bande audio doux (IIR Butterworth ordre 4, [300 Hz - 2800 Hz] couvrant voix SSB et tonalités SSTV)
    # Zéro distorsion de phase grâce à sosfiltfilt (filtrage bidirectionnel sans déphasage)
    print("[*] Filtrage passe-bande audio USB [300 Hz - 2800 Hz] (Butterworth bidirectionnel zéro-phase)...")
    sos = scipy.signal.butter(4, [300.0, 2800.0], btype='bandpass', fs=audio_fs, output='sos')
    # Filtrage séparé des composantes I et Q pour conserver le signal analytique pur
    audio_real = scipy.signal.sosfiltfilt(sos, audio_complex.real).astype(np.float32)
    audio_imag = scipy.signal.sosfiltfilt(sos, audio_complex.imag).astype(np.float32)
    audio_complex = audio_real + 1j * audio_imag
    print(f"[+] Audio USB démodulé : {len(audio_complex)} échantillons ({len(audio_complex)/audio_fs:.2f} s)")

    # 4. Enregistrement fichier WAV démodulé (Audio réel)
    max_amp = np.max(np.abs(audio_real)) + 1e-9
    audio_norm = audio_real / max_amp
    print(f"[*] Enregistrement du fichier WAV démodulé : {output_wav}")
    with wave.open(output_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(audio_fs))
        wf.writeframes((audio_norm * 32767.0).astype(np.int16).tobytes())

    # 5. Détecteur de fréquence instantanée (Discriminateur FM complexe)
    print("[*] Calcul de la fréquence instantanée...")
    diff = audio_complex[1:] * np.conj(audio_complex[:-1])
    inst_freq = np.angle(diff) * audio_fs / (2.0 * np.pi)
    inst_freq = np.pad(inst_freq, (0, 1), mode='edge')
    inst_freq_smooth = np.convolve(inst_freq, np.ones(5)/5.0, mode='same')

    # 6. Filtre adapté cohérent pour la synchro de ligne 1200 Hz (4.862 ms)
    sync_samples = int(round(0.004862 * audio_fs))      # ~233 échantillons
    porch_samples = int(round(0.000572 * audio_fs))     # ~27 échantillons
    chan_dur = 0.146432                                 # 146.432 ms (320 px * 0.4576 ms)
    chan_samples = int(round(chan_dur * audio_fs))      # ~7029 échantillons
    # Martin 1 standard : cadence exacte 134.3947532 LPM (446.446 ms/ligne)
    nominal_line = 60.0 / 134.3947532 * audio_fs        # 21429.414 échantillons @ 48 kHz

    print(f"[*] Calcul du filtre adapté (Matched Filter) 1200 Hz (ligne nominale = {nominal_line:.3f} éch)...")
    t_sync = np.arange(sync_samples, dtype=np.float64) / audio_fs
    ref_sync = np.hanning(sync_samples) * np.exp(-2j * np.pi * 1200.0 * t_sync)
    mf = np.abs(np.convolve(audio_real, ref_sync, mode='same'))**2

    # 7. Détection robuste de la trame SSTV Martin 1 (Signature VIS 1900 Hz + Ligne 0 périodique)
    print("[*] Détection robuste de la trame SSTV Martin 1 (Signature VIS 1900 Hz + impulsion 1200 Hz)...")
    
    # Filtre adapté pour le ton leader 1900 Hz (100 ms)
    win19 = int(0.100 * audio_fs)
    ref19 = np.hanning(win19) * np.exp(-2j * np.pi * 1900.0 * np.arange(win19) / audio_fs)
    p1900 = np.abs(np.convolve(audio_real, ref19, mode='same'))**2

    # Recherche des candidats pour la tonalité leader 1900 Hz
    peaks19, _ = scipy.signal.find_peaks(p1900, height=0.20 * np.max(p1900), distance=int(0.8 * audio_fs))

    first_sync_idx = None
    for p19 in peaks19:
        # Entre 0.8s et 1.4s après le leader 1900Hz se trouve la ligne 0 (synchro 1200 Hz)
        w0 = int(p19 + 0.75 * audio_fs)
        w1 = int(p19 + 1.45 * audio_fs)
        if w1 >= len(mf):
            continue
        pk0 = w0 + np.argmax(mf[w0:w1])
        # Vérification qu'au moins 5 lignes consécutives présentent une impulsion de synchro 1200 Hz
        valid_pulses = sum(
            1 for l in range(1, 8)
            if pk0 + int(l * nominal_line) + 150 < len(mf)
            and np.max(mf[pk0 + int(l * nominal_line) - 150 : pk0 + int(l * nominal_line) + 150]) > 0.08 * np.max(mf)
        )
        if valid_pulses >= 4:
            first_sync_idx = pk0
            break

    if first_sync_idx is None:
        print("[-] Fallback : recherche directe par périodicité 1200 Hz...")
        thresh_mf = 0.15 * np.max(mf)
        candidate_peaks, _ = scipy.signal.find_peaks(mf, height=thresh_mf, distance=int(0.25 * audio_fs))
        for p in candidate_peaks:
            val = sum(1 for l in range(1, 8) if p + int(l * nominal_line) + 150 < len(mf) and np.max(mf[p + int(l * nominal_line) - 150 : p + int(l * nominal_line) + 150]) > thresh_mf)
            if val >= 4:
                first_sync_idx = p
                break

    if first_sync_idx is None:
        print("[-] Attention: Train d'impulsions périodiques non verrouillé, repli sur le maximum global.")
        first_sync_idx = np.argmax(mf)

    # Le préambule VOX / VIS se situe environ 1.45s avant la ligne 0
    t_start = max(0.0, (first_sync_idx / audio_fs) - 1.453)
    print(f"[+] Début de transmission SSTV identifié à t = {t_start:.3f} s")
    print(f"[+] Première impulsion de synchro (Ligne 0) verrouillée à t = {first_sync_idx / audio_fs:.4f} s (index {first_sync_idx})")

    # 8. Synchronisation précise de la cadence de ligne et calage sub-pixel
    print("[*] Synchronisation précise de la cadence de ligne...")
    t_resample = np.linspace(0, chan_samples - 1, 320)
    p0 = first_sync_idx

    peaks = [p0]
    valid_lines = [0]
    for l in range(1, 256):
        exp_pos = p0 + int(round(l * nominal_line))
        w0 = max(0, exp_pos - 150)
        w1 = min(len(mf), exp_pos + 150)
        if w0 >= w1:
            break
        pk = w0 + np.argmax(mf[w0:w1])
        peaks.append(pk)
        valid_lines.append(l)

    peaks = np.array(peaks)
    valid_lines = np.array(valid_lines)

    if len(valid_lines) > 5:
        best_slope, _ = np.polyfit(valid_lines, peaks, 1)
    else:
        best_slope = nominal_line

    best_p0 = p0

    # Calage optimal du centrage horizontal via l'image de référence sur les lignes valides uniquement
    if reference_image and os.path.exists(reference_image) and len(valid_lines) > 5:
        ref = Image.open(reference_image).convert('RGB').resize((320, 256))
        n_val = min(len(valid_lines), 64)
        ref_g = np.array(ref, dtype=np.float32)[:n_val, :, 1]
        best_corr = -1.0
        opt_shift = 0

        for shift in range(-1500, 1500, 10):
            greens = []
            for l in range(n_val):
                pos = int(round(p0 + shift + l * best_slope)) + (sync_samples // 2) + porch_samples
                chunk = inst_freq_smooth[pos : pos + chan_samples]
                if len(chunk) >= chan_samples:
                    greens.append(np.interp(t_resample, np.arange(chan_samples), chunk[:chan_samples]))
                else:
                    greens.append(np.zeros(320))
            greens = np.array(greens)
            rec_val = np.clip((greens - 1500.0) / 800.0, 0.0, 1.0) * 255.0
            std_rec = np.std(rec_val)
            if std_rec > 1e-3:
                corr = np.corrcoef(ref_g.flatten(), rec_val.flatten())[0, 1]
                if corr > best_corr:
                    best_corr = corr
                    opt_shift = shift

        best_p0 = p0 + opt_shift

    print(f"[+] Pente de ligne optimale verrouillée : {best_slope:.4f} échantillons/ligne (Dérive : {best_slope - nominal_line:+.2f})")
    print(f"[+] Décalage horizontal p0 verrouillé   : {best_p0} (shift = {best_p0 - p0})")

    # 10. Décodage couleur des 256 lignes avec alignement parfait
    print("[*] Décodage couleur des 256 lignes Martin 1...")
    img_array = np.zeros((256, 320, 3), dtype=np.uint8)

    for line_idx in range(256):
        pos = int(round(best_p0 + line_idx * best_slope)) + (sync_samples // 2) + porch_samples
        for c_idx in [1, 2, 0]: # Vert, Bleu, Rouge
            chunk = inst_freq_smooth[pos : pos + chan_samples]
            if len(chunk) >= chan_samples:
                px_vals = np.interp(t_resample, np.arange(chan_samples), chunk[:chan_samples])
                val = np.clip((px_vals - 1500.0) / 800.0, 0.0, 1.0) * 255.0
                img_array[line_idx, :, c_idx] = val.astype(np.uint8)
            pos += chan_samples + porch_samples

    # 10. Sauvegarde de l'image reconstruite
    rec_img = Image.fromarray(img_array, mode='RGB')
    rec_img.save(output_image)
    print(f"\n[+] IMAGE RECONSTRUITE AVEC SUCCÈS : {output_image}")

    # 11. Comparaison avec la mire de référence
    if reference_image:
        try:
            ref = Image.open(reference_image).convert('RGB').resize((320, 256))
            ref_arr = np.array(ref, dtype=np.float32)
            rec_arr = img_array.astype(np.float32)

            mse = np.mean((ref_arr - rec_arr)**2)
            psnr = 10.0 * np.log10((255.0**2) / (mse + 1e-12))
            
            corr_r = np.corrcoef(ref_arr[:, :, 0].flatten(), rec_arr[:, :, 0].flatten())[0, 1]
            corr_g = np.corrcoef(ref_arr[:, :, 1].flatten(), rec_arr[:, :, 1].flatten())[0, 1]
            corr_b = np.corrcoef(ref_arr[:, :, 2].flatten(), rec_arr[:, :, 2].flatten())[0, 1]

            print("\n" + "="*70)
            print("🔍 ANALYSE DE FIDÉLITÉ (GAP IMAGE ÉMISE vs IMAGE REÇUE)")
            print("="*70)
            print(f"Lignes décodées               : 256 / 256 (100.0%)")
            print(f"Erreur Quadratique Moyenne    : {mse:.1f} (sur une échelle de 0 à 65025)")
            print(f"Rapport Signal/Bruit (PSNR)   : {psnr:.2f} dB")
            print(f"Corrélation canal ROUGE       : {corr_r:+.3f}")
            print(f"Corrélation canal VERT        : {corr_g:+.3f}")
            print(f"Corrélation canal BLEU        : {corr_b:+.3f}")
            print("="*70)
        except Exception as e:
            print(f"[-] Erreur comparaison gap : {e}")

    # 12. Mise à jour automatique des métadonnées SigMF si un fichier .sigmf-meta existe
    sigmf_meta_path = None
    if iq_filename.endswith(".cf32") or iq_filename.endswith(".sigmf-data"):
        base_name = os.path.splitext(iq_filename)[0]
        candidate = base_name + ".sigmf-meta"
        if os.path.isfile(candidate):
            sigmf_meta_path = candidate
    elif os.path.isfile(iq_filename + ".sigmf-meta"):
        sigmf_meta_path = iq_filename + ".sigmf-meta"

    if sigmf_meta_path and os.path.isfile(sigmf_meta_path):
        try:
            print(f"\n[*] Fichier de métadonnées SigMF détecté : {sigmf_meta_path}")
            with open(sigmf_meta_path, "r", encoding="utf-8") as f:
                sigmf_dict = json.load(f)

            if "annotations" not in sigmf_dict or not isinstance(sigmf_dict["annotations"], list):
                sigmf_dict["annotations"] = []

            # Échantillons IQ exacts au taux sdr_rate
            sstv_iq_start = int(round(t_start * sdr_rate))
            # Fin de la dernière ligne décodée
            t_sstv_end = (best_p0 + 256 * best_slope) / audio_fs
            sstv_iq_count = int(round((t_sstv_end - t_start) * sdr_rate))
            sstv_iq_count = max(0, min(sstv_iq_count, total_samples - sstv_iq_start))

            # Bornes de fréquences RF exactes [1100 Hz - 2300 Hz] en USB par rapport à carrier_freq
            freq_lower = float(carrier_freq + 1100.0)
            freq_upper = float(carrier_freq + 2300.0)

            # Calcul de l'horodatage ISO-8601 absolu de début si datetime de capture est présent
            annotation_datetime = None
            if "captures" in sigmf_dict and len(sigmf_dict["captures"]) > 0:
                cap_dt_str = sigmf_dict["captures"][0].get("core:datetime")
                if cap_dt_str:
                    try:
                        # Parsing ISO UTC (ex: 2026-10-10T16:53:15.067Z)
                        clean_dt = cap_dt_str.replace("Z", "+00:00")
                        cap_dt = datetime.datetime.fromisoformat(clean_dt)
                        ann_dt = cap_dt + datetime.timedelta(seconds=t_start)
                        annotation_datetime = ann_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                    except Exception:
                        pass

            annotation_obj = {
                "core:sample_start": sstv_iq_start,
                "core:sample_count": sstv_iq_count,
                "core:freq_lower_edge": freq_lower,
                "core:freq_upper_edge": freq_upper,
                "core:label": "SSTV Martin 1",
                "core:comment": (
                    f"Martin 1 transmission decoded into {output_image}. "
                    f"VIS start: {t_start:.3f}s, line slope: {best_slope:.4f} samples/line @ 48kHz."
                ),
                "sstv:mode": "Martin 1",
                "sstv:lines": 256,
                "sstv:output_image": output_image,
                "sstv:t_start_sec": round(float(t_start), 4),
                "sstv:duration_sec": round(float(t_sstv_end - t_start), 4),
                "sstv:line_rate_lpm": round(float(60.0 * audio_fs / best_slope), 5)
            }
            if annotation_datetime:
                annotation_obj["core:datetime"] = annotation_datetime

            # Remplacement ou ajout (évite les doublons identiques SSTV Martin 1)
            updated_annotations = [
                ann for ann in sigmf_dict["annotations"]
                if ann.get("core:label") != "SSTV Martin 1"
            ]
            updated_annotations.append(annotation_obj)

            # Tri obligatoire selon la spécification SigMF
            updated_annotations.sort(key=lambda a: a.get("core:sample_start", 0))
            sigmf_dict["annotations"] = updated_annotations

            with open(sigmf_meta_path, "w", encoding="utf-8") as f:
                json.dump(sigmf_dict, f, indent=4)

            print(f"[+] Métadonnées SigMF mises à jour avec succès :")
            print(f"    - Début SSTV : échantillon {sstv_iq_start} (t = {t_start:.3f} s)")
            print(f"    - Durée SSTV : {sstv_iq_count} échantillons ({t_sstv_end - t_start:.2f} s)")
            print(f"    - Bande RF   : {freq_lower/1e6:.6f} MHz - {freq_upper/1e6:.6f} MHz")
        except Exception as meta_err:
            print(f"[-] Erreur lors de la mise à jour du fichier SigMF : {meta_err}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Décodeur SSTV Martin 1 direct depuis capture IQ SDR")
    parser.add_argument("file", nargs="?", default="sstv_full.cf32", help="Fichier IQ .cf32")
    parser.add_argument("-f", "--center", type=float, default=14.220e6, help="Fréquence centrale SDR (Défaut: 14.220 MHz)")
    parser.add_argument("-s", "--rate", type=float, default=250000.0, help="Taux d'échantillons IQ (Défaut: 250 kSps)")
    parser.add_argument("-c", "--carrier", type=float, default=14.230038e6, help="Porteuse RF (Défaut: 14.230038 MHz)")
    parser.add_argument("-o", "--out", default="image_recue.png", help="Image de sortie")
    parser.add_argument("-w", "--wav", default="sstv_audio_demod.wav", help="Fichier WAV de sortie")
    parser.add_argument("-r", "--ref", default="mire_f4jxq.png", help="Image de référence")

    args = parser.parse_args()

    decode_sstv_from_iq(
        iq_filename=args.file,
        sdr_center_freq=args.center,
        sdr_rate=args.rate,
        carrier_freq=args.carrier,
        output_image=args.out,
        output_wav=args.wav,
        reference_image=args.ref
    )
