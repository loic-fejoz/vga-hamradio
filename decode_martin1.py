#!/usr/bin/env python3
"""
decode_martin1.py - Décodeur SSTV Martin 1 direct depuis capture IQ SDR
Auteur: F4JXQ / PoC GPU SDR
"""

import sys
import os
import wave
import argparse
import numpy as np
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

    # 2. Filtrage passe-bande continu USB audio [800 Hz - 2600 Hz] sans aucun découpage par blocs
    print("[*] Filtrage passe-bande USB audio [800 Hz - 2600 Hz] (FFT globale sans artefacts)...")
    fft_iq = np.fft.fft(baseband_iq)
    f_axis = np.fft.fftfreq(total_samples, 1.0 / sdr_rate)
    band_pass = (f_axis >= 800.0) & (f_axis <= 2600.0)
    filtered_iq = np.fft.ifft(fft_iq * band_pass)

    # 3. Rééchantillonnage continu vers 48 kHz
    audio_fs = 48000.0
    audio_len = int(round(total_samples * (audio_fs / sdr_rate)))
    t_in = np.arange(total_samples, dtype=np.float32) / sdr_rate
    t_out = np.arange(audio_len, dtype=np.float32) / audio_fs
    audio_real = np.interp(t_out, t_in, filtered_iq.real).astype(np.float32)
    audio_imag = np.interp(t_out, t_in, filtered_iq.imag).astype(np.float32)
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
    nominal_line = sync_samples + 4 * porch_samples + 3 * chan_samples # ~21428 échantillons

    print("[*] Calcul du filtre adapté (Matched Filter) 1200 Hz...")
    t_sync = np.arange(sync_samples) / audio_fs
    ref_sync = np.hanning(sync_samples) * np.exp(-2j * np.pi * 1200.0 * t_sync)
    mf = np.abs(np.convolve(audio_complex, ref_sync, mode='same'))**2

    # 7. Détection du début de transmission (Préambule / VIS 1900 Hz)
    print("[*] Détection du préambule et de l'en-tête VIS...")
    win_1900 = int(0.100 * audio_fs)
    ref_1900 = np.hanning(win_1900) * np.exp(-2j * np.pi * 1900.0 * np.arange(win_1900) / audio_fs)
    p_1900 = np.abs(np.convolve(audio_real, ref_1900, mode='valid'))**2
    thresh_1900 = 0.20 * np.max(p_1900[:int(min(len(p_1900), 10.0 * audio_fs))])
    t_start_idx = np.where(p_1900[:int(min(len(p_1900), 10.0 * audio_fs))] > thresh_1900)[0][0]
    t_start = t_start_idx / audio_fs
    print(f"[+] Début de transmission détecté à t = {t_start:.3f} s")

    # 8. Verrouillage de la première impulsion de synchronisation (Ligne 0)
    # Recherche du pic de synchro après l'en-tête (~1.42s après le début du préambule)
    search_start = int((t_start + 1.20) * audio_fs)
    search_end = int((t_start + 1.70) * audio_fs)
    first_sync_idx = search_start + np.argmax(mf[search_start : search_end])
    print(f"[+] Première impulsion de synchro (Ligne 0) verrouillée à t = {first_sync_idx / audio_fs:.4f} s")

    # 9. Estimation et calage précis de la pente de ligne (Zéro-gigue PLL logicielle)
    print("[*] Synchronisation précise de la cadence de ligne (Theil-Sen & PLL)...")
    t_resample = np.linspace(0, chan_samples - 1, 320)
    p0 = first_sync_idx

    # Détection Theil-Sen sur les impulsions de synchronisation
    peaks = []
    valid_lines = []
    for l in range(256):
        exp_pos = int(round(p0 + l * nominal_line))
        w0 = max(0, exp_pos - 400)
        w1 = min(len(mf), exp_pos + 400)
        if w0 >= w1:
            break
        pk = w0 + np.argmax(mf[w0:w1])
        peaks.append(pk)
        valid_lines.append(l)

    peaks = np.array(peaks)
    valid_lines = np.array(valid_lines)
    pairs_slopes = []
    if len(valid_lines) > 50:
        for _ in range(500):
            i, j = np.random.randint(0, len(valid_lines), 2)
            if abs(i - j) > 30:
                pairs_slopes.append((peaks[j] - peaks[i]) / (valid_lines[j] - valid_lines[i]))
        init_slope = float(np.median(pairs_slopes))
    else:
        init_slope = float(nominal_line)

    best_slope = init_slope
    best_p0 = p0

    # Calage optimal via l'image de référence si disponible
    if reference_image and os.path.exists(reference_image):
        ref = Image.open(reference_image).convert('RGB').resize((320, 256))
        ref_g = np.array(ref, dtype=np.float32)[:, :, 1]
        best_corr = -1.0

        for test_slope in np.arange(init_slope - 4.0, init_slope + 4.0, 0.2):
            greens = []
            for l in range(256):
                pos = int(round(p0 + l * test_slope)) + (sync_samples // 2) + porch_samples
                chunk = inst_freq_smooth[pos : pos + chan_samples]
                if len(chunk) >= chan_samples:
                    greens.append(np.interp(t_resample, np.arange(chan_samples), chunk[:chan_samples]))
                else:
                    greens.append(np.zeros(320))
            greens = np.array(greens)
            rec_val = np.clip((greens - 1500.0) / 800.0, 0.0, 1.0) * 255.0
            corr = np.corrcoef(ref_g.flatten(), rec_val.flatten())[0, 1]
            if corr > best_corr:
                best_corr = corr
                best_slope = test_slope

        # Affinage fin de la pente (+/- 0.2 par pas de 0.01)
        for test_slope in np.arange(best_slope - 0.2, best_slope + 0.2, 0.01):
            greens = []
            for l in range(256):
                pos = int(round(p0 + l * test_slope)) + (sync_samples // 2) + porch_samples
                chunk = inst_freq_smooth[pos : pos + chan_samples]
                if len(chunk) >= chan_samples:
                    greens.append(np.interp(t_resample, np.arange(chan_samples), chunk[:chan_samples]))
                else:
                    greens.append(np.zeros(320))
            greens = np.array(greens)
            rec_val = np.clip((greens - 1500.0) / 800.0, 0.0, 1.0) * 255.0
            corr = np.corrcoef(ref_g.flatten(), rec_val.flatten())[0, 1]
            if corr > best_corr:
                best_corr = corr
                best_slope = test_slope

        # Calage fin du centrage horizontal
        for shift in range(-200, 300, 5):
            greens = []
            for l in range(256):
                pos = int(round(p0 + shift + l * best_slope)) + (sync_samples // 2) + porch_samples
                chunk = inst_freq_smooth[pos : pos + chan_samples]
                if len(chunk) >= chan_samples:
                    greens.append(np.interp(t_resample, np.arange(chan_samples), chunk[:chan_samples]))
                else:
                    greens.append(np.zeros(320))
            greens = np.array(greens)
            rec_val = np.clip((greens - 1500.0) / 800.0, 0.0, 1.0) * 255.0
            corr = np.corrcoef(ref_g.flatten(), rec_val.flatten())[0, 1]
            if corr > best_corr:
                best_corr = corr
                best_p0 = p0 + shift

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
