#!/usr/bin/env python3
"""
vga_sstv.py - Émetteur Radio SSTV (Martin 1) / Tonalité / Porteuse CW via GPU RAMDAC
Auteur: F4JXQ / GPU SDR PoC (Version corrigée)
"""

import argparse
import sys
import time
import subprocess
import gc
import threading
import struct
import os
import numpy as np
from PIL import Image

try:
    import moderngl
    import glfw
except ImportError:
    moderngl = None
    glfw = None


# ==============================================================================
# 1. SHADER GLSL : SYNTHÈSE NUMÉRIQUE DIRECTE (DDS) & MÉLANGEUR USB
# ==============================================================================

VERTEX_SHADER = """
#version 330 core
in vec2 in_position;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""

FRAGMENT_SHADER_CW = """
#version 330 core
out vec4 FragColor;
uniform uint u_screen_height;
uniform uint u_htotal;
uniform uint u_frame_phase;
uniform uint u_phase_inc;
const float TWO_PI = 6.28318530717958647692;
const float UINT_SCALE = TWO_PI / 4294967296.0;

void main() {
    uint y_scan = (u_screen_height - 1u) - uint(floor(gl_FragCoord.y));
    uint x_scan = uint(floor(gl_FragCoord.x));
    uint sample_in_frame = (y_scan * u_htotal) + x_scan;
    uint carrier_phase_uint = u_frame_phase + (sample_in_frame * u_phase_inc);
    float rf = cos(float(carrier_phase_uint) * UINT_SCALE);
    FragColor = vec4(0.5 + 0.5 * rf, 0.0, 0.0, 1.0);
}
"""

FRAGMENT_SHADER_TONE = """
#version 330 core
out vec4 FragColor;
uniform uint u_screen_height;
uniform uint u_htotal;
uniform uint u_frame_phase;
uniform uint u_phase_inc;
uniform uint u_tone_frame_phase;
uniform uint u_tone_phase_inc;
const float TWO_PI = 6.28318530717958647692;
const float UINT_SCALE = TWO_PI / 4294967296.0;

void main() {
    uint y_scan = (u_screen_height - 1u) - uint(floor(gl_FragCoord.y));
    uint x_scan = uint(floor(gl_FragCoord.x));
    uint sample_in_frame = (y_scan * u_htotal) + x_scan;
    uint carrier_phase_uint = u_frame_phase + (sample_in_frame * u_phase_inc);
    uint tone_phase_uint = u_tone_frame_phase + (sample_in_frame * u_tone_phase_inc);
    float rf = cos(float(carrier_phase_uint + tone_phase_uint) * UINT_SCALE);
    FragColor = vec4(0.5 + 0.5 * rf, 0.0, 0.0, 1.0);
}
"""

FRAGMENT_SHADER_SSTV = """
#version 330 core
out vec4 FragColor;

uniform uint u_screen_height;
uniform uint u_htotal;
uniform uint u_frame_phase;
uniform uint u_phase_inc;

uniform sampler2D u_iq_texture;
uniform uint u_audio_frame_base_int;
uniform float u_audio_frame_base_frac;
uniform float u_audio_advance_per_sample;
uniform uint u_total_audio_samples;

const float TWO_PI = 6.28318530717958647692;
const float UINT_SCALE = TWO_PI / 4294967296.0;

void main() {
    uint y_scan = (u_screen_height - 1u) - uint(floor(gl_FragCoord.y));
    uint x_scan = uint(floor(gl_FragCoord.x));
    uint sample_in_frame = (y_scan * u_htotal) + x_scan;
    uint carrier_phase_uint = u_frame_phase + (sample_in_frame * u_phase_inc);
    float carrier_phase = float(carrier_phase_uint) * UINT_SCALE;

    float advance = u_audio_frame_base_frac + (float(sample_in_frame) * u_audio_advance_per_sample);
    uint advance_int = uint(advance);
    float frac = advance - float(advance_int);
    uint total_sample_int = u_audio_frame_base_int + advance_int;

    if (total_sample_int >= u_total_audio_samples) {
        FragColor = vec4(0.5, 0.0, 0.0, 1.0);
        return;
    }

    int s0_x = int(total_sample_int & 2047u);
    int s0_y = int(total_sample_int >> 11);
    vec2 s0 = texelFetch(u_iq_texture, ivec2(s0_x, s0_y), 0).rg;

    uint next_sample_int = min(total_sample_int + 1u, u_total_audio_samples - 1u);
    int s1_x = int(next_sample_int & 2047u);
    int s1_y = int(next_sample_int >> 11);
    vec2 s1 = texelFetch(u_iq_texture, ivec2(s1_x, s1_y), 0).rg;

    vec2 iq = mix(s0, s1, frac);

    // Synthèse BLU / USB exacte : I * cos(wc) - Q * sin(wc)
    float rf = (iq.r * cos(carrier_phase)) - (iq.g * sin(carrier_phase));

    // Sortie analogique normalisée (0.0V à 0.7V sur broche Rouge VGA)
    float dac = 0.5 + 0.5 * rf;

    // Dithering triangulaire sub-pixel temporel (linéarisation du DAC 8-bit, élimine distorsion et raies parasites)
    float seed = dot(gl_FragCoord.xy, vec2(12.9898, 78.233)) + float(u_frame_phase % 10000u) * 0.1337;
    float dither = fract(sin(seed) * 43758.5453) - 0.5;
    dac += dither / 255.0;

    FragColor = vec4(dac, 0.0, 0.0, 1.0);
}
"""

# ==============================================================================
# 2. GÉNÉRATEUR AUDIO BANDE DE BASE SSTV (MARTIN 1) EN CPU
# ==============================================================================

def generate_martin1_baseband(image_path, audio_fs=48000):
    """
    Génère la piste audio I/Q complète pour le mode Martin 1 (320x256).
    Structure exacte Martin 1 (Conforme pySSTV / slowrx / spécification officielle) :
      - Préambule VOX/AGC (500 ms @ 1900 Hz + 10 ms break @ 1200 Hz)
      - En-tête VIS standard :
          Leader 1 (1900 Hz, 300 ms) + Break (1200 Hz, 10 ms) + Leader 2 (1900 Hz, 300 ms)
          Start bit (1200 Hz, 30 ms) + VIS code 0x2C (8x30 ms) + Stop bit (1200 Hz, 30 ms)
      - 256 lignes de balayage G-B-R :
          Sync (1200 Hz, 4.862 ms)
          Porche (1500 Hz, 0.572 ms)
          Vert (146.432 ms)
          Séparateur (1500 Hz, 0.572 ms)
          Bleu (146.432 ms)
          Séparateur (1500 Hz, 0.572 ms)
          Rouge (146.432 ms)
          Séparateur final (1500 Hz, 0.572 ms)
      - Durée stricte par ligne : 446.446 ms (21430 échantillons @ 48 kHz).
    """
    print(f"[*] Pré-calcul de la modulation SSTV Martin 1 (Fs = {audio_fs} Hz)...")
    
    # 1. Chargement et redimensionnement de l'image
    img = Image.open(image_path).convert('RGB')
    img = img.resize((320, 256), Image.Resampling.LANCZOS)
    img_data = np.array(img, dtype=np.float32) / 255.0  # Shape: (256, 320, 3)

    # 2. Construction de la séquence de fréquence instantanée
    freq_segments = []
    
    def add_tone(freq, duration_sec):
        num_s = int(round(duration_sec * audio_fs))
        if num_s > 0:
            freq_segments.append(np.full(num_s, freq, dtype=np.float32))

    # --- 0. PRÉAMBULE VOX / AGC (POUR STABILISER LE GAIN SDR & DÉCODEUR) ---
    add_tone(1900.0, 0.500)   # Préambule VOX/AGC (500 ms)
    add_tone(1200.0, 0.010)   # Break (10 ms)

    # --- 1. EN-TÊTE DE CALIBRATION ET CODE VIS (MARTIN 1 STANDARD) ---
    add_tone(1900.0, 0.300)   # Leader 1 (300 ms)
    add_tone(1200.0, 0.010)   # Break (10 ms)
    add_tone(1900.0, 0.300)   # Leader 2 (300 ms)
    add_tone(1200.0, 0.030)   # VIS start bit (30 ms)
    
    # Code VIS Martin 1 = 44 (0x2C, bits LSB: 0, 0, 1, 1, 0, 1, 0, parité=1)
    vis_bits = [0, 0, 1, 1, 0, 1, 0, 1]
    for bit in vis_bits:
        add_tone(1100.0 if bit == 1 else 1300.0, 0.030)
    add_tone(1200.0, 0.030)   # VIS stop bit

    # --- 2. 256 LIGNES DE BALAYAGE COULEUR (MARTIN 1 CADENCE EXACTE 134.3947532 LPM) ---
    # Durée théorique absolue par ligne : 60 / 134.3947532 = 0.446446132 s
    t_line = 60.0 / 134.3947532
    t_sync = 0.004862
    t_gap = 0.000572
    t_scan = 0.146432

    # Horodatage absolu au niveau échantillon pour chaque ligne : ZÉRO accumulation d'arrondi !
    line_starts = [int(round(l * t_line * audio_fs)) for l in range(257)]

    for line in range(256):
        s_line = line_starts[line]
        s_next = line_starts[line + 1]

        # Bornes exactes des 8 segments au sein de cette ligne
        s1 = s_line + int(round(t_sync * audio_fs))
        s2 = s_line + int(round((t_sync + t_gap) * audio_fs))
        s3 = s_line + int(round((t_sync + t_gap + t_scan) * audio_fs))
        s4 = s_line + int(round((t_sync + 2 * t_gap + t_scan) * audio_fs))
        s5 = s_line + int(round((t_sync + 2 * t_gap + 2 * t_scan) * audio_fs))
        s6 = s_line + int(round((t_sync + 3 * t_gap + 2 * t_scan) * audio_fs))
        s7 = s_line + int(round((t_sync + 3 * t_gap + 3 * t_scan) * audio_fs))
        s8 = s_next

        # 1. Synchro ligne (1200 Hz, 4.862 ms)
        freq_segments.append(np.full(s1 - s_line, 1200.0, dtype=np.float32))
        # 2. Porche synchro (1500 Hz, 0.572 ms)
        freq_segments.append(np.full(s2 - s1, 1500.0, dtype=np.float32))

        # 3. Balayage VERT (146.432 ms)
        nG = s3 - s2
        g_vals = img_data[line, :, 1]
        freq_g = np.interp(np.linspace(0, 319, nG, endpoint=False), np.arange(320), 1500.0 + (g_vals * 800.0)).astype(np.float32)
        freq_segments.append(freq_g)

        # 4. Séparateur (1500 Hz, 0.572 ms)
        freq_segments.append(np.full(s4 - s3, 1500.0, dtype=np.float32))

        # 5. Balayage BLEU (146.432 ms)
        nB = s5 - s4
        b_vals = img_data[line, :, 2]
        freq_b = np.interp(np.linspace(0, 319, nB, endpoint=False), np.arange(320), 1500.0 + (b_vals * 800.0)).astype(np.float32)
        freq_segments.append(freq_b)

        # 6. Séparateur (1500 Hz, 0.572 ms)
        freq_segments.append(np.full(s6 - s5, 1500.0, dtype=np.float32))

        # 7. Balayage ROUGE (146.432 ms)
        nR = s7 - s6
        r_vals = img_data[line, :, 0]
        freq_r = np.interp(np.linspace(0, 319, nR, endpoint=False), np.arange(320), 1500.0 + (r_vals * 800.0)).astype(np.float32)
        freq_segments.append(freq_r)

        # 8. Séparateur final (1500 Hz, 0.572 ms)
        freq_segments.append(np.full(s8 - s7, 1500.0, dtype=np.float32))

    all_freqs = np.concatenate(freq_segments)
    total_samples = len(all_freqs)
    total_duration = total_samples / audio_fs
    
    # 3. Intégration de la phase continue en float64 haute précision (zéro gigue, zéro saut de fréquence)
    cycles = (np.cumsum(all_freqs / audio_fs, dtype=np.float64)) % 1.0
    phase = (2.0 * np.pi * cycles).astype(np.float32)

    # 4. Génération I/Q cartésienne en float32 (haute fidélité sans bruit de troncature)
    i_signal = np.cos(phase, dtype=np.float32)
    q_signal = np.sin(phase, dtype=np.float32)
    
    # 5. Rangement dans une texture 2D (largeur 2^11 = 2048)
    tex_w = 2048
    tex_h = int(np.ceil(total_samples / tex_w))
    pad_samples = (tex_w * tex_h) - total_samples
    
    if pad_samples > 0:
        i_signal = np.pad(i_signal, (0, pad_samples), mode='constant')
        q_signal = np.pad(q_signal, (0, pad_samples), mode='constant')
        
    tex_data = np.empty((tex_h, tex_w, 2), dtype=np.float32)
    tex_data[:, :, 0] = i_signal.reshape((tex_h, tex_w))
    tex_data[:, :, 1] = q_signal.reshape((tex_h, tex_w))
    
    print(f"[+] Audio SSTV pré-calculé : {total_samples} échantillons ({total_duration:.2f} s)")
    print(f"[+] Texture I/Q allouée en VRAM : {tex_w}x{tex_h} (RG32F, {tex_data.nbytes / 1024**2:.1f} Mo)")
    
    return tex_data.tobytes(), total_samples, tex_w, tex_h, total_duration


def save_texture_file(filepath, iq_bytes, total_samples, tex_w, tex_h, total_duration, audio_fs=48000):
    """Enregistre la texture I/Q et ses métadonnées dans un format binaire standard .sstvtex."""
    magic = b"VGASSTV1"
    version = 1
    data_bytes = len(iq_bytes)
    header = struct.pack("<8sIIIIIdI32s", magic, version, int(audio_fs), int(total_samples),
                         int(tex_w), int(tex_h), float(total_duration), data_bytes, b"\x00"*32)
    with open(filepath, "wb") as f:
        f.write(header)
        f.write(iq_bytes)
    print(f"[+] Texture I/Q sauvegardée avec succès dans : {filepath} ({len(header) + data_bytes} octets)")


def load_texture_file(filepath):
    """Charge une texture I/Q pré-calculée depuis un fichier .sstvtex."""
    with open(filepath, "rb") as f:
        header_bytes = f.read(72)
        if len(header_bytes) < 72:
            raise ValueError(f"Fichier texture corrompu ou trop court : {filepath}")
        magic, version, audio_fs, total_samples, tex_w, tex_h, total_duration, data_bytes, _ = struct.unpack(
            "<8sIIIIIdI32s", header_bytes
        )
        if magic != b"VGASSTV1":
            raise ValueError(f"Format de fichier invalide (Magic={magic}) dans {filepath}")
        iq_bytes = f.read(data_bytes)
        if len(iq_bytes) != data_bytes:
            raise ValueError(f"Données de texture tronquées dans {filepath}")
    print(f"[+] Texture I/Q chargée depuis {filepath} : {tex_w}x{tex_h} ({total_samples} éch., {total_duration:.2f} s)")
    return iq_bytes, total_samples, tex_w, tex_h, total_duration, audio_fs


# ==============================================================================
# 3. GESTION DE L'ÉMETTEUR GPU
# ==============================================================================

def run_transmitter(mode=2, image_path=None, iq_precomputed=None, carrier_freq=14230000.0, tone_freq=1900.0,
                    pixel_clock=148500000.0, screen_width=1920, screen_height=1080,
                    htotal=2200, vtotal=1125, fullscreen=False, monitor_index=0, duration=120.0):
    
    if moderngl is None or glfw is None:
        print("Erreur: Dépendances OpenGL Python manquantes (moderngl, glfw).")
        print("        Installez-les via: pip install moderngl glfw, ou utilisez le moteur C/C++ via --cpp.")
        sys.exit(1)

    mode_names = {0: "PORTEUSE PURE (CW)", 1: f"TONALITÉ FIXE ({tone_freq:.1f} Hz)", 2: "SSTV MARTIN 1"}
    print("\n" + "="*70)
    print(f"📻 ÉMETTEUR SDR GPU RAMDAC (PYTHON) - MODE : {mode_names[mode]}")
    print("="*70)
    print(f"[*] Fréquence porteuse RF : {carrier_freq / 1e6:.6f} MHz")
    print(f"[*] Pixel Clock ($f_clk$)  : {pixel_clock / 1e6:.3f} MHz")
    print(f"[*] Timings d'affichage   : {screen_width}x{screen_height} (H_total: {htotal}, V_total: {vtotal})")
    print(f"[*] Sortie physique       : Broche 1 VGA (Rouge) + Broche 6 (Masse)")
    print("="*70)

    # 1. Initialisation GLFW
    if not glfw.init():
        print("[-] Erreur critique : Impossible d'initialiser GLFW.")
        sys.exit(1)

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.RESIZABLE, glfw.FALSE)

    monitors = glfw.get_monitors()
    target_monitor = None
    if fullscreen:
        if len(monitors) > 0:
            target_monitor = monitors[min(monitor_index, len(monitors) - 1)]
            m_name = glfw.get_monitor_name(target_monitor).decode('utf-8', errors='ignore')
            print(f"[+] Plein écran activé sur moniteur #{monitor_index} ({m_name})")
            target_refresh = int(round(pixel_clock / (htotal * vtotal)))
            glfw.window_hint(glfw.REFRESH_RATE, target_refresh)
        else:
            print("[!] Aucun moniteur GLFW détecté. Tentative en fenêtre normale...")

    window = glfw.create_window(screen_width, screen_height, "VGA SDR Transmitter", target_monitor, None)
    if not window:
        glfw.terminate()
        print("[-] Impossible de créer la fenêtre GLFW.")
        print("    Vérifiez que votre affichage X11 est actif avec ./setup_display.sh")
        sys.exit(1)

    # Vérification post-création pour synchroniser avec les timings exacts
    active_now = detect_active_display_timings()
    if active_now:
        act_pclk, act_htotal, act_vtotal, act_w, act_h = active_now
        if act_pclk != pixel_clock or act_htotal != htotal or act_vtotal != vtotal:
            print(f"[+] Synchro active confirmée : {act_pclk/1e6:.3f} MHz (H={act_htotal}, V={act_vtotal})")
            pixel_clock, htotal, vtotal = act_pclk, act_htotal, act_vtotal

    glfw.make_context_current(window)
    glfw.swap_interval(1)

    ctx = moderngl.create_context()
    print(f"[+] GPU Actif : {ctx.info.get('GL_RENDERER')}")
    print(f"[+] Version OpenGL : {ctx.info.get('GL_VERSION')}")

    # 2. Compilation Shader dédié au mode actif
    if mode == 0:
        fs = FRAGMENT_SHADER_CW
    elif mode == 1:
        fs = FRAGMENT_SHADER_TONE
    else:
        fs = FRAGMENT_SHADER_SSTV
    prog = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=fs)
    
    # Constantes géométriques
    samples_per_frame = int(htotal * vtotal)
    prog['u_screen_height'].value = int(screen_height)
    prog['u_htotal'].value = int(htotal)

    # Calcul incrément de phase porteuse (DDS 32 bits exact)
    # inc = round(2^32 * f_c / f_clk)
    phase_inc = int(round((2**32) * (carrier_freq / pixel_clock))) % (2**32)
    prog['u_phase_inc'].value = phase_inc

    # Mode 1 : Tonalité fixe
    if mode == 1:
        tone_phase_inc = int(round((2**32) * (tone_freq / pixel_clock))) % (2**32)
        prog['u_tone_phase_inc'].value = tone_phase_inc

    # Mode 2 : SSTV
    iq_tex = None
    total_audio_samples = 0
    if mode == 2:
        audio_fs = 48000
        if iq_precomputed is not None:
            iq_bytes, total_audio_samples, tex_w, tex_h, total_duration, audio_fs = iq_precomputed
        else:
            if not image_path:
                print("[-] Erreur : Une image ou texture est requise en mode SSTV.")
                sys.exit(1)
            iq_bytes, total_audio_samples, tex_w, tex_h, total_duration = generate_martin1_baseband(image_path, audio_fs)

        if duration is None or duration >= 120.0:
            duration = total_duration
        else:
            duration = min(duration, total_duration)
        
        iq_tex = ctx.texture((tex_w, tex_h), 2, iq_bytes, dtype='f4')
        iq_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        iq_tex.use(location=0)
        
        prog['u_iq_texture'].value = 0
        prog['u_audio_advance_per_sample'].value = float(audio_fs / pixel_clock)
        prog['u_total_audio_samples'].value = int(total_audio_samples)

    # Quad plein écran
    vertices = np.array([
        -1.0, -1.0,
         1.0, -1.0,
        -1.0,  1.0,
        -1.0,  1.0,
         1.0, -1.0,
         1.0,  1.0,
    ], dtype='f4')
    vbo = ctx.buffer(vertices.tobytes())
    vao = ctx.simple_vertex_array(prog, vbo, 'in_position')

    # 3. Boucle de transmission
    print(f"\n🚀 ÉMISSION EN COURS (Durée : {duration:.1f} s)...")
    if mode == 0:
        print("   -> Émission d'une porteuse pure (CW). Vérifiez la fréquence sur votre SDR.")
    elif mode == 1:
        print(f"   -> Émission d'une tonalité fixe de {tone_freq} Hz en USB.")
    elif mode == 2:
        print("   -> Émission SSTV Martin 1 en cours. Ouvrez QSSTV ou Robot36 !")

    frame_idx = 0
    start_time = time.perf_counter()
    last_swap = start_time
    late_frames = 0
    frame_holder = [0]
    stop_progress = threading.Event()

    def progress_worker():
        while not stop_progress.is_set():
            idx = frame_holder[0]
            t_el = (idx * samples_per_frame) / pixel_clock
            pct = min(100.0, (t_el / duration) * 100.0)
            sys.stdout.write(f"\r⏳ Progression : [{pct:5.1f}%] - {t_el:5.1f}s / {duration:.1f}s (Frame #{idx})")
            sys.stdout.flush()
            stop_progress.wait(1.0)

    progress_thread = threading.Thread(target=progress_worker, daemon=True)
    progress_thread.start()

    gc.disable()
    try:
        while True:
            # Calcul de la phase de départ de cette trame en entier 64-bit modulo 2^32 exact
            # Zéro dérive, zéro gigue OS !
            frame_phase = (frame_idx * samples_per_frame * phase_inc) % (2**32)
            prog['u_frame_phase'].value = int(frame_phase)

            if mode == 1:
                tone_frame_phase = (frame_idx * samples_per_frame * tone_phase_inc) % (2**32)
                prog['u_tone_frame_phase'].value = int(tone_frame_phase)

            if mode == 2:
                total_audio_sample = (frame_idx * samples_per_frame) * (audio_fs / pixel_clock)
                base_int = int(total_audio_sample)
                base_frac = float(total_audio_sample - base_int)
                prog['u_audio_frame_base_int'].value = base_int
                prog['u_audio_frame_base_frac'].value = base_frac

            # Rendu GPU
            vao.render()
            glfw.swap_buffers(window)
            glfw.poll_events()

            if glfw.window_should_close(window):
                print("\n[!] Arrêt demandé par l'utilisateur.")
                break

            t_elapsed = (frame_idx * samples_per_frame) / pixel_clock
            frame_holder[0] = frame_idx

            if t_elapsed >= duration:
                break

            # Diagnostic de cadence : détection des trames manquées (GPU trop lent)
            now = time.perf_counter()
            if frame_idx > 0:
                dt = now - last_swap
                if dt > 1.5 * (samples_per_frame / pixel_clock):
                    late_frames += 1
            last_swap = now

            frame_idx += 1

    except KeyboardInterrupt:
        print("\n[!] Arrêt manuel (Ctrl+C).")
    finally:
        stop_progress.set()
        progress_thread.join(timeout=0.5)
        gc.enable()
        print("\n\n✅ Transmission terminée avec succès !")
        wall = time.perf_counter() - start_time
        theo = (frame_idx * samples_per_frame) / pixel_clock
        if wall > 0 and frame_idx > 0:
            print(f"[i] Cadence réelle : {frame_idx / wall:.2f} trames/s "
                  f"(théorique {pixel_clock / samples_per_frame:.2f}) | "
                  f"temps mural {wall:.2f} s vs théorique {theo:.2f} s | "
                  f"trames en retard : {late_frames} ({100.0 * late_frames / frame_idx:.1f} %)")
        if iq_tex:
            iq_tex.release()
        glfw.destroy_window(window)
        glfw.terminate()


# ==============================================================================
# 4. CLI
# ==============================================================================

def detect_active_display_timings():
    """Détecte dynamiquement la résolution active, le Pixel Clock et H_total / V_total via xrandr."""
    try:
        res = subprocess.run(["xrandr", "--verbose"], capture_output=True, text=True, timeout=2.0)
        lines = res.stdout.splitlines()
        for i, line in enumerate(lines):
            if "*current" in line:
                parts = line.strip().split()
                pclk = None
                for p in parts:
                    if p.endswith("MHz"):
                        pclk = float(p[:-3]) * 1e6
                        break
                width = None
                htotal = None
                if i + 1 < len(lines) and "total" in lines[i + 1]:
                    h_parts = lines[i + 1].strip().split()
                    if "width" in h_parts:
                        w_idx = h_parts.index("width")
                        width = int(h_parts[w_idx + 1])
                    if "total" in h_parts:
                        tot_idx = h_parts.index("total")
                        htotal = int(h_parts[tot_idx + 1])
                height = None
                vtotal = None
                if i + 2 < len(lines) and "total" in lines[i + 2]:
                    v_parts = lines[i + 2].strip().split()
                    if "height" in v_parts:
                        h_idx = v_parts.index("height")
                        height = int(v_parts[h_idx + 1])
                    if "total" in v_parts:
                        tot_idx = v_parts.index("total")
                        vtotal = int(v_parts[tot_idx + 1])
                
                if pclk and htotal and vtotal:
                    return pclk, htotal, vtotal, width or 1920, height or 1080
    except Exception:
        pass
    return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Émetteur Radio via GPU RAMDAC (SSTV, Tonalité fixe, Porteuse CW)"
    )
    parser.add_argument("image", nargs="?", default=None, help="Chemin vers l'image source (requis pour SSTV)")
    parser.add_argument("--cw", action="store_true", help="Mode CW : Porteuse pure pour calibration SDR")
    parser.add_argument("--tone", type=float, default=None, help="Mode TONE : Tonalité fixe en Hz (ex: 1900.0)")
    parser.add_argument("-f", "--freq", type=float, default=14.230e6,
                        help="Fréquence porteuse RF en Hz (Défaut: 14.230 MHz)")
    parser.add_argument("--pclk", type=float, default=None,
                        help="Pixel Clock du mode vidéo en Hz (Auto-détecté par défaut via xrandr)")
    parser.add_argument("--width", type=int, default=None, help="Largeur active (Auto-détecté par défaut)")
    parser.add_argument("--height", type=int, default=None, help="Hauteur active (Auto-détecté par défaut)")
    parser.add_argument("--htotal", type=int, default=None, help="H_total (Auto-détecté par défaut via xrandr)")
    parser.add_argument("--vtotal", type=int, default=None, help="V_total (Auto-détecté par défaut via xrandr)")
    parser.add_argument("-d", "--duration", type=float, default=None,
                        help="Durée en secondes (Défaut: automatique pour SSTV ~115s, 30s pour CW/TONE)")
    parser.add_argument("--fullscreen", action="store_true", help="Plein écran sur la sortie sélectionnée")
    parser.add_argument("--monitor", type=int, default=0, help="Index du moniteur pour le plein écran")
    
    # Nouvelles options pour le moteur C/C++ et la sérialisation de textures
    parser.add_argument("--save-texture", "--export-texture", type=str, default=None,
                        help="Enregistre la texture I/Q calculée dans un fichier binaire .sstvtex")
    parser.add_argument("--load-texture", "--input-texture", type=str, default=None,
                        help="Charge une texture I/Q pré-enregistrée depuis un fichier .sstvtex")
    parser.add_argument("--export-only", "--no-tx", action="store_true",
                        help="Génère/sauvegarde la texture sans lancer l'émission GPU")
    parser.add_argument("--cpp", "--use-cpp", action="store_true",
                        help="Délègue le rendu et le scanout GPU au programme C/C++ ultra-déterministe (vga_tx_gpu)")
    parser.add_argument("-r", "--realtime", action="store_true",
                        help="Active la priorité temps réel SCHED_FIFO (avec le moteur C/C++)")

    args = parser.parse_args()

    # Détection automatique des timings si non spécifiés
    detected = detect_active_display_timings()
    det_pclk, det_htotal, det_vtotal, det_w, det_h = detected if detected else (148.0e6, 1184, 610, 1024, 576)

    if args.pclk is not None and detected and abs(args.pclk - det_pclk) > 1e6:
        print(f"[!] ATTENTION : Le mode d'affichage physique est {det_pclk/1e6:.3f} MHz ({det_htotal}x{det_vtotal}),")
        print(f"    mais vous avez forcé --pclk {args.pclk/1e6:.3f} MHz !")
        print(f"    -> Cela va multiplier la vitesse audio par {det_pclk/args.pclk:.2f}x et décaler la porteuse RF !")
        print(f"    -> Conseil : Ne spécifiez PAS --pclk pour laisser le script s'adapter automatiquement.")

    pclk = args.pclk if args.pclk is not None else det_pclk
    htotal = args.htotal if args.htotal is not None else (det_htotal if args.pclk is None else (2200 if pclk < 200e6 else 2080))
    vtotal = args.vtotal if args.vtotal is not None else (det_vtotal if args.pclk is None else (1125 if pclk < 200e6 else 1144))
    width = args.width if args.width is not None else det_w
    height = args.height if args.height is not None else det_h

    if args.pclk is None and detected:
        print(f"[+] Timings d'affichage auto-détectés : {pclk/1e6:.3f} MHz ({width}x{height}), H_total={htotal}, V_total={vtotal}")
    else:
        print(f"[*] Timings d'affichage appliqués : {pclk/1e6:.3f} MHz ({width}x{height}), H_total={htotal}, V_total={vtotal}")

    if args.cw:
        op_mode = 0
    elif args.tone is not None:
        op_mode = 1
    else:
        op_mode = 2

    # Gestion de la texture SSTV (génération, sauvegarde, chargement)
    iq_data = None
    tex_filepath = args.load_texture

    if op_mode == 2:
        if args.load_texture:
            iq_data = load_texture_file(args.load_texture)
        elif args.image:
            audio_fs = 48000
            iq_bytes, total_audio_samples, tex_w, tex_h, total_duration = generate_martin1_baseband(args.image, audio_fs)
            iq_data = (iq_bytes, total_audio_samples, tex_w, tex_h, total_duration, audio_fs)
            if args.save_texture:
                save_texture_file(args.save_texture, iq_bytes, total_audio_samples, tex_w, tex_h, total_duration, audio_fs)
                tex_filepath = args.save_texture
        else:
            print("Erreur: Vous devez spécifier une image, une texture (--load-texture) ou utiliser --cw / --tone <FREQ>.")
            sys.exit(1)

        if args.export_only:
            print("[+] Export terminé. Arrêt demandé (--export-only).")
            sys.exit(0)

    duration = args.duration
    if duration is None:
        if op_mode in (0, 1):
            duration = 30.0
        elif iq_data is not None:
            duration = iq_data[4]

    # Exécution via moteur C/C++ (si demandé) ou Python natif
    if args.cpp:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cpp_bin = os.path.join(script_dir, "vga_tx_gpu")
        if not os.path.isfile(cpp_bin):
            print(f"[*] Compilation du binaire C/C++ {cpp_bin} via make...")
            subprocess.run(["make", "vga_tx_gpu"], cwd=script_dir, check=True)

        cpp_cmd = [cpp_bin, "-f", str(args.freq), "--pclk", str(pclk),
                   "--width", str(width), "--height", str(height),
                   "--htotal", str(htotal), "--vtotal", str(vtotal),
                   "-d", str(duration)]
        if args.fullscreen:
            cpp_cmd.append("--fullscreen")
            cpp_cmd.extend(["--monitor", str(args.monitor)])
        if args.realtime:
            cpp_cmd.append("--realtime")

        if op_mode == 0:
            cpp_cmd.append("--cw")
        elif op_mode == 1:
            cpp_cmd.extend(["--tone", str(args.tone if args.tone is not None else 1900.0)])
        else:
            if not tex_filepath:
                tex_filepath = "/dev/shm/temp_tx.sstvtex"
                save_texture_file(tex_filepath, iq_data[0], iq_data[1], iq_data[2], iq_data[3], iq_data[4], iq_data[5])
            cpp_cmd.extend(["-i", tex_filepath])

        print(f"[*] Lancement du moteur C/C++ : {' '.join(cpp_cmd)}")
        subprocess.run(cpp_cmd)
    else:
        run_transmitter(
            mode=op_mode,
            image_path=args.image,
            iq_precomputed=iq_data,
            carrier_freq=args.freq,
            tone_freq=args.tone if args.tone is not None else 1900.0,
            pixel_clock=pclk,
            screen_width=width,
            screen_height=height,
            htotal=htotal,
            vtotal=vtotal,
            fullscreen=args.fullscreen,
            monitor_index=args.monitor,
            duration=duration
        )

