#!/usr/bin/env python3
"""
Generic Voice SSB (Upper Sideband) Texture Generator for vga-hamradio
Accepts any audio file (WAV, MP3, etc.) or synthesizes speech via Edge-TTS (fr-FR-DeniseNeural).
Automatically converts compressed formats (MP3) to WAV using ffmpeg.
Applies SSB speech bandpass filtering (300 Hz - 2800 Hz), computes the analytic
Hilbert transform (I/Q), and exports the binary .sstvtex texture compatible with vga_sstv.py and vga_tx_gpu.
"""

import os
import sys
import struct
import argparse
import subprocess
import numpy as np
import scipy.signal
import scipy.io.wavfile as wav

DEFAULT_TEXT = "Ceci est un test mené par F4JXQ Foxtrot four Juliet X-Ray Quebec pour générer de la SSB à partir d'une carte graphique."
DEFAULT_VOICE = "fr-FR-DeniseNeural"
AUDIO_FS = 48000  # Standard audio sample rate for the vga-hamradio pipeline


def generate_tts_audio(text, voice, output_mp3):
    """Generates the MP3 audio file using edge-tts."""
    print(f"[*] Speech synthesis via Edge-TTS (Voice: {voice})...")
    print(f"    Text: \"{text}\"")
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", voice,
        "--text", text,
        "--write-media", output_mp3
    ]
    subprocess.run(cmd, check=True)
    if not os.path.isfile(output_mp3) or os.path.getsize(output_mp3) == 0:
        raise RuntimeError(f"Failed to generate MP3 audio file: {output_mp3}")
    print(f"[+] Audio generated: {output_mp3} ({os.path.getsize(output_mp3)} bytes)")


def convert_audio_to_wav(input_path, output_wav, target_fs=AUDIO_FS):
    """Converts any audio format (MP3, OGG, FLAC, etc.) to 16-bit PCM mono WAV at target_fs using ffmpeg."""
    print(f"[*] Converting '{input_path}' to WAV PCM {target_fs} Hz mono via ffmpeg...")
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", input_path,
        "-ar", str(target_fs),
        "-ac", "1",
        output_wav
    ]
    subprocess.run(cmd, check=True)
    if not os.path.isfile(output_wav) or os.path.getsize(output_wav) == 0:
        raise RuntimeError(f"ffmpeg conversion failed for: {input_path}")
    print(f"[+] Converted WAV ready: {output_wav}")


def process_audio_to_ssb_iq(wav_path, target_fs=AUDIO_FS, lowcut=300.0, highcut=2800.0,
                            pad_silence=0.5, apply_filter=True, peak_target=0.95):
    """
    Loads WAV audio, filters speech SSB bandwidth (300-2800 Hz),
    adds lead-in and lead-out silence padding, calculates the Hilbert transform,
    and normalizes the complex envelope dynamic range.
    """
    sr, raw_audio = wav.read(wav_path)
    if raw_audio.dtype == np.int16:
        audio = raw_audio.astype(np.float32) / 32768.0
    elif raw_audio.dtype == np.int32:
        audio = raw_audio.astype(np.float32) / 2147483648.0
    elif raw_audio.dtype in (np.float32, np.float64):
        audio = raw_audio.astype(np.float32)
    elif raw_audio.dtype == np.uint8:
        audio = (raw_audio.astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported audio format: {raw_audio.dtype}")

    # Convert stereo / multichannel to mono
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Resample if sample rate does not match target
    if sr != target_fs:
        print(f"[*] Resampling from {sr} Hz to {target_fs} Hz...")
        num_target = int(round(len(audio) * target_fs / sr))
        audio = scipy.signal.resample(audio, num_target).astype(np.float32)
        sr = target_fs

    # Speech SSB bandpass filter (suppresses DC carrier leakage and out-of-band energy)
    if apply_filter:
        print(f"[*] Bandpass filtering speech SSB [{lowcut:.0f} Hz - {highcut:.0f} Hz]...")
        sos = scipy.signal.butter(4, [lowcut, highcut], btype='bandpass', fs=sr, output='sos')
        audio_filt = scipy.signal.sosfiltfilt(sos, audio).astype(np.float32)
    else:
        print("[*] Bandpass filter disabled by user.")
        audio_filt = audio

    # Add lead-in and lead-out silence (settles receiver AGC and avoids transient truncation)
    pad_samples = int(round(pad_silence * sr))
    if pad_samples > 0:
        audio_padded = np.pad(audio_filt, (pad_samples, pad_samples), mode='constant')
    else:
        audio_padded = audio_filt

    print(f"[*] Computing analytic quadrature component via Hilbert Transform...")
    # Complex analytic signal: z(t) = m(t) + j * H[m(t)]
    z = scipy.signal.hilbert(audio_padded)

    # Normalize complex envelope to maximize DAC dynamic range without clipping
    env = np.abs(z)
    peak = np.max(env)
    if peak > 0:
        z = (z / peak) * peak_target

    I = np.real(z).astype(np.float32)
    Q = np.imag(z).astype(np.float32)

    duration = len(I) / sr
    print(f"[+] Analytic SSB signal ready: {len(I)} samples ({duration:.2f} s)")
    print(f"    Normalized peak envelope: {np.max(np.abs(I + 1j*Q)):.3f}")

    return I, Q, sr, duration


def build_and_save_texture(I, Q, audio_fs, output_sstvtex):
    """
    Builds the 2D RG32F texture (2048 x H) and saves the binary .sstvtex file
    using the standard header structure expected by vga_sstv.py and vga_tx_gpu.
    VGASSTV1 binary header structure (72 bytes):
      - magic: 8 bytes ("VGASSTV1")
      - version: uint32 (1)
      - audio_fs: uint32 (48000)
      - total_samples: uint32
      - tex_w: uint32 (2048)
      - tex_h: uint32
      - total_duration: float64 (double)
      - data_bytes: uint32
      - reserved: 32 bytes
    """
    total_samples = len(I)
    total_duration = total_samples / audio_fs

    tex_w = 2048
    tex_h = int(np.ceil(total_samples / tex_w))
    pad_samples = (tex_w * tex_h) - total_samples

    if pad_samples > 0:
        I_padded = np.pad(I, (0, pad_samples), mode='constant')
        Q_padded = np.pad(Q, (0, pad_samples), mode='constant')
    else:
        I_padded = I
        Q_padded = Q

    tex_data = np.empty((tex_h, tex_w, 2), dtype=np.float32)
    tex_data[:, :, 0] = I_padded.reshape((tex_h, tex_w))
    tex_data[:, :, 1] = Q_padded.reshape((tex_h, tex_w))

    iq_bytes = tex_data.tobytes()

    magic = b"VGASSTV1"
    version = 1
    data_bytes = len(iq_bytes)
    header = struct.pack(
        "<8sIIIIIdI32s",
        magic,
        version,
        int(audio_fs),
        int(total_samples),
        int(tex_w),
        int(tex_h),
        float(total_duration),
        data_bytes,
        b"\x00" * 32
    )

    with open(output_sstvtex, "wb") as f:
        f.write(header)
        f.write(iq_bytes)

    print(f"[+] I/Q Texture saved: {output_sstvtex}")
    print(f"    Dimensions: {tex_w}x{tex_h} pixels (Format RG32F, {len(header) + data_bytes} bytes)")
    print(f"    Total duration: {total_duration:.2f} seconds")


def main():
    parser = argparse.ArgumentParser(
        description="Universal Voice SSB (Upper Sideband) Texture Generator for vga-hamradio (.sstvtex)\n"
                    "Accepts any audio file (WAV, MP3, etc.) or synthesizes speech via Edge-TTS.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", nargs="?", default=None,
                        help="Input audio file (WAV, MP3, OGG, FLAC...). If omitted, uses --text.")
    parser.add_argument("-i", "--input-file", dest="input_opt", default=None,
                        help="Alternative option to specify the input audio file.")
    parser.add_argument("-o", "--output", default=None,
                        help="Output texture file (.sstvtex). Default: <input_basename>.sstvtex")
    parser.add_argument("-t", "--text", default=None,
                        help="Text to synthesize via Edge-TTS (if no audio file is provided). Default: F4JXQ test message.")
    parser.add_argument("-v", "--voice", default=DEFAULT_VOICE,
                        help=f"Edge-TTS voice (default: {DEFAULT_VOICE})")
    parser.add_argument("--lowcut", type=float, default=300.0,
                        help="High-pass cutoff frequency of speech filter in Hz (default: 300)")
    parser.add_argument("--highcut", type=float, default=2800.0,
                        help="Low-pass cutoff frequency of speech filter in Hz (default: 2800)")
    parser.add_argument("--no-filter", action="store_true",
                        help="Disable bandpass filtering (if audio is already pre-filtered/mastered)")
    parser.add_argument("--pad", type=float, default=0.5,
                        help="Lead-in and lead-out silence padding in seconds (default: 0.5s)")
    parser.add_argument("--peak", type=float, default=0.95,
                        help="Target peak envelope normalization level (default: 0.95)")
    parser.add_argument("--wav-check", default=None,
                        help="Export a verification WAV file (for listening to the in-phase I signal)")

    args = parser.parse_args()

    audio_source = args.input or args.input_opt
    temp_files = []

    try:
        # 1. Obtain 48 kHz mono PCM WAV file
        if audio_source:
            if not os.path.isfile(audio_source):
                print(f"[-] Error: Specified file does not exist: {audio_source}", file=sys.stderr)
                sys.exit(1)

            base_name, ext = os.path.splitext(audio_source)
            ext_lower = ext.lower()

            # Deduce output texture filename if not specified
            if args.output is None:
                args.output = f"{base_name}.sstvtex"

            # Check if input is MP3 or any non-WAV format
            if ext_lower != ".wav":
                print(f"[!] '{ext}' format detected ({audio_source}). Automatic conversion via ffmpeg required.")
                temp_wav = f"/dev/shm/temp_converted_{os.getpid()}.wav"
                temp_files.append(temp_wav)
                convert_audio_to_wav(audio_source, temp_wav, target_fs=AUDIO_FS)
                wav_to_process = temp_wav
            else:
                # WAV file: check whether sample rate is 48 kHz and mono
                try:
                    sr, data = wav.read(audio_source)
                    if sr != AUDIO_FS or data.ndim > 1:
                        print(f"[*] Adapting input WAV ({sr} Hz, {data.ndim} channels) to {AUDIO_FS} Hz mono...")
                        temp_wav = f"/dev/shm/temp_resampled_{os.getpid()}.wav"
                        temp_files.append(temp_wav)
                        convert_audio_to_wav(audio_source, temp_wav, target_fs=AUDIO_FS)
                        wav_to_process = temp_wav
                    else:
                        wav_to_process = audio_source
                except Exception as e:
                    # In case of exotic WAV header / codec, delegate to ffmpeg
                    print(f"[*] Non-standard WAV read ({e}), normalizing via ffmpeg...")
                    temp_wav = f"/dev/shm/temp_ffmpeg_{os.getpid()}.wav"
                    temp_files.append(temp_wav)
                    convert_audio_to_wav(audio_source, temp_wav, target_fs=AUDIO_FS)
                    wav_to_process = temp_wav

        else:
            # Edge-TTS Speech Synthesis Mode
            text_to_speak = args.text or DEFAULT_TEXT
            if args.output is None:
                args.output = "voice_denise_ssb.sstvtex"

            temp_mp3 = f"/dev/shm/temp_edge_tts_{os.getpid()}.mp3"
            temp_wav = f"/dev/shm/temp_edge_tts_48k_{os.getpid()}.wav"
            temp_files.extend([temp_mp3, temp_wav])

            generate_tts_audio(text_to_speak, args.voice, temp_mp3)
            convert_audio_to_wav(temp_mp3, temp_wav, target_fs=AUDIO_FS)
            wav_to_process = temp_wav

        # 2. Process analytic I/Q SSB signal
        I, Q, sr, duration = process_audio_to_ssb_iq(
            wav_to_process,
            target_fs=AUDIO_FS,
            lowcut=args.lowcut,
            highcut=args.highcut,
            pad_silence=args.pad,
            apply_filter=not args.no_filter,
            peak_target=args.peak
        )

        # 3. Construct and export binary .sstvtex texture
        build_and_save_texture(I, Q, sr, args.output)

        # 4. Optional verification audio export
        if args.wav_check:
            wav.write(args.wav_check, sr, (I * 32767.0).astype(np.int16))
            print(f"[+] Verification audio exported to: {args.wav_check}")

        print("\n" + "="*70)
        print("🎉 SSB texture ready for GPU transmission!")
        print(f"   Texture file: {args.output}")
        print(f"   Duration: {duration:.2f} s")
        print("="*70)

    finally:
        for tmp in temp_files:
            if os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
