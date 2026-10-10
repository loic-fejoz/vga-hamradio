#!/usr/bin/env python3
"""
concat_textures.py - Concatène plusieurs fichiers textures I/Q (.sstvtex) en une seule texture.

Format VGASSTV1:
  - Header binaire 72 octets :
      magic (8s: "VGASSTV1"), version (uint32: 1), audio_fs (uint32),
      total_samples (uint32), tex_w (uint32: 2048), tex_h (uint32),
      total_duration (float64/double), data_bytes (uint32), reserved (32s)
  - Données I/Q : tex_w * tex_h paires de float32 (RG32F)
"""

import argparse
import os
import struct
import sys
import numpy as np

HEADER_FORMAT = "<8sIIIIIdI32s"
HEADER_SIZE = 72
MAGIC = b"VGASSTV1"
TEXTURE_WIDTH = 2048


def read_texture_file(filepath):
    """
    Lit un fichier texture .sstvtex et extrait les échantillons I/Q réels (non paddés).
    Retourne (iq_samples, audio_fs, header_dict).
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Fichier introuvable : '{filepath}'")

    file_size = os.path.getsize(filepath)
    if file_size < HEADER_SIZE:
        raise ValueError(f"Fichier trop court ({file_size} octets) : '{filepath}'")

    with open(filepath, "rb") as f:
        header_bytes = f.read(HEADER_SIZE)
        magic, version, audio_fs, total_samples, tex_w, tex_h, total_duration, data_bytes, _ = struct.unpack(
            HEADER_FORMAT, header_bytes
        )

        if magic != MAGIC:
            raise ValueError(f"Signature magique invalide ({magic}) dans '{filepath}' (attendu: {MAGIC})")

        expected_size = HEADER_SIZE + data_bytes
        if file_size < expected_size:
            raise ValueError(
                f"Fichier tronqué : '{filepath}' (taille actuelle: {file_size}, attendue: {expected_size})"
            )

        raw_data = f.read(data_bytes)
        if len(raw_data) != data_bytes:
            raise ValueError(f"Impossible de lire l'intégralité des données ({len(raw_data)}/{data_bytes} octets)")

    # Décodage float32 RG32F (chaque pixel = 2 floats: I, Q)
    data_arr = np.frombuffer(raw_data, dtype=np.float32).reshape(-1, 2)

    # Récupérer uniquement les total_samples utiles (ignorer le padding de fin de texture)
    if total_samples > len(data_arr):
        raise ValueError(
            f"Incohérence dans '{filepath}' : total_samples ({total_samples}) > taille des données ({len(data_arr)})"
        )

    valid_samples = data_arr[:total_samples]

    meta = {
        "version": version,
        "audio_fs": audio_fs,
        "total_samples": total_samples,
        "tex_w": tex_w,
        "tex_h": tex_h,
        "total_duration": total_duration,
        "data_bytes": data_bytes,
    }

    return valid_samples, audio_fs, meta


def write_texture_file(filepath, iq_samples, audio_fs, tex_w=TEXTURE_WIDTH):
    """
    Écrit le tableau d'échantillons I/Q dans un fichier texture .sstvtex au format standard VGASSTV1.
    """
    total_samples = len(iq_samples)
    total_duration = total_samples / float(audio_fs) if audio_fs > 0 else 0.0

    tex_h = int(np.ceil(total_samples / float(tex_w))) if total_samples > 0 else 1
    pad_samples = (tex_w * tex_h) - total_samples

    if pad_samples > 0:
        padding = np.zeros((pad_samples, 2), dtype=np.float32)
        tex_data = np.vstack([iq_samples, padding])
    else:
        tex_data = iq_samples

    tex_data = tex_data.astype(np.float32)
    iq_bytes = tex_data.tobytes()
    data_bytes = len(iq_bytes)

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        1,  # version
        int(audio_fs),
        int(total_samples),
        int(tex_w),
        int(tex_h),
        float(total_duration),
        data_bytes,
        b"\x00" * 32,
    )

    with open(filepath, "wb") as f:
        f.write(header)
        f.write(iq_bytes)

    return total_samples, tex_w, tex_h, total_duration, len(header) + data_bytes


def main():
    parser = argparse.ArgumentParser(
        description="Concatène plusieurs fichiers textures I/Q (.sstvtex) en un seul avec insertion optionnelle de silence."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="FICHIER",
        help="Chemins vers les fichiers textures .sstvtex à concaténer",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        metavar="SORTIE",
        help="Nom du fichier texture de résultat (.sstvtex)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=0.0,
        metavar="SECONDES",
        help="Délai en secondes de blanc/silence à insérer entre chaque fichier (défaut: 0.0)",
    )

    args = parser.parse_args()

    if args.delay < 0:
        parser.error("Le délai ne peut pas être négatif.")

    if len(args.inputs) == 0:
        parser.error("Au moins un fichier d'entrée est requis.")

    print(f"[*] Concaténation de {len(args.inputs)} fichier(s) texture...")
    if args.delay > 0:
        print(f"[*] Silence inter-fichiers : {args.delay:.3f} s")

    collected_segments = []
    base_fs = None

    for idx, filepath in enumerate(args.inputs):
        try:
            samples, fs, meta = read_texture_file(filepath)
        except Exception as e:
            print(f"[-] Erreur lors de la lecture de '{filepath}': {e}", file=sys.stderr)
            sys.exit(1)

        print(
            f"  [{idx + 1}/{len(args.inputs)}] {filepath}: "
            f"{meta['total_samples']} éch., {meta['total_duration']:.2f} s, fs={fs} Hz, "
            f"texture {meta['tex_w']}x{meta['tex_h']}"
        )

        if base_fs is None:
            base_fs = fs
        elif fs != base_fs:
            print(
                f"[-] Erreur d'incompatibilité de fréquence d'échantillonnage pour '{filepath}': "
                f"{fs} Hz != {base_fs} Hz (fréquence du premier fichier)",
                file=sys.stderr,
            )
            sys.exit(1)

        # Insertion du délai de blanc entre les fichiers (avant chaque fichier sauf le premier)
        if idx > 0 and args.delay > 0:
            delay_samples_count = int(round(args.delay * base_fs))
            if delay_samples_count > 0:
                silence = np.zeros((delay_samples_count, 2), dtype=np.float32)
                collected_segments.append(silence)

        collected_segments.append(samples)

    if not collected_segments:
        print("[-] Aucun échantillon à concaténer.", file=sys.stderr)
        sys.exit(1)

    combined_samples = np.vstack(collected_segments)

    try:
        total_samples, tex_w, tex_h, total_duration, file_size = write_texture_file(
            args.output, combined_samples, base_fs, tex_w=TEXTURE_WIDTH
        )
    except Exception as e:
        print(f"[-] Erreur lors de l'écriture du fichier résultat '{args.output}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Texture concaténée enregistrée avec succès : {args.output}")
    print(f"    - Échantillons totaux : {total_samples}")
    print(f"    - Durée totale        : {total_duration:.2f} s")
    print(f"    - Fréquence audio     : {base_fs} Hz")
    print(f"    - Dimensions texture  : {tex_w}x{tex_h} (RG32F)")
    print(f"    - Taille fichier      : {file_size} octets ({file_size / (1024 * 1024):.2f} Mo)")


if __name__ == "__main__":
    main()
