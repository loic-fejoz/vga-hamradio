#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <math.h>
#include <time.h>
#include <pthread.h>
#include <sched.h>
#include <unistd.h>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <GL/gl.h>
#include <GL/glx.h>
#include <GL/glxext.h>

// =============================================================================
// TYPES ET DÉCLARATIONS OPENGL 3.3 CORE SANS DÉPENDANCE EXTERNE
// =============================================================================
#ifndef GL_CLAMP_TO_EDGE
#define GL_CLAMP_TO_EDGE 0x812F
#endif
#ifndef GL_TEXTURE0
#define GL_TEXTURE0 0x84C0
#endif
#ifndef GL_FRAGMENT_SHADER
#define GL_FRAGMENT_SHADER 0x8B30
#endif
#ifndef GL_VERTEX_SHADER
#define GL_VERTEX_SHADER 0x8B31
#endif
#ifndef GL_COMPILE_STATUS
#define GL_COMPILE_STATUS 0x8B81
#endif
#ifndef GL_LINK_STATUS
#define GL_LINK_STATUS 0x8B82
#endif
#ifndef GL_ARRAY_BUFFER
#define GL_ARRAY_BUFFER 0x8892
#endif
#ifndef GL_STATIC_DRAW
#define GL_STATIC_DRAW 0x88E4
#endif
#ifndef GL_RG
#define GL_RG 0x8227
#endif
#ifndef GL_RG32F
#define GL_RG32F 0x822F
#endif

typedef char GLchar;
typedef ptrdiff_t GLsizeiptr;
typedef ptrdiff_t GLintptr;

typedef GLuint (*PFN_glCreateShader) (GLenum type);
typedef void (*PFN_glShaderSource) (GLuint shader, GLsizei count, const GLchar *const*string, const GLint *length);
typedef void (*PFN_glCompileShader) (GLuint shader);
typedef void (*PFN_glGetShaderiv) (GLuint shader, GLenum pname, GLint *params);
typedef void (*PFN_glGetShaderInfoLog) (GLuint shader, GLsizei bufSize, GLsizei *length, GLchar *infoLog);
typedef void (*PFN_glDeleteShader) (GLuint shader);
typedef GLuint (*PFN_glCreateProgram) (void);
typedef void (*PFN_glAttachShader) (GLuint program, GLuint shader);
typedef void (*PFN_glLinkProgram) (GLuint program);
typedef void (*PFN_glGetProgramiv) (GLuint program, GLenum pname, GLint *params);
typedef void (*PFN_glGetProgramInfoLog) (GLuint program, GLsizei bufSize, GLsizei *length, GLchar *infoLog);
typedef void (*PFN_glDeleteProgram) (GLuint program);
typedef void (*PFN_glUseProgram) (GLuint program);
typedef GLint (*PFN_glGetUniformLocation) (GLuint program, const GLchar *name);
typedef void (*PFN_glUniform1i) (GLint location, GLint v0);
typedef void (*PFN_glUniform1ui) (GLint location, GLuint v0);
typedef void (*PFN_glUniform1f) (GLint location, GLfloat v0);
typedef void (*PFN_glGenVertexArrays) (GLsizei n, GLuint *arrays);
typedef void (*PFN_glBindVertexArray) (GLuint array);
typedef void (*PFN_glDeleteVertexArrays) (GLsizei n, const GLuint *arrays);
typedef void (*PFN_glGenBuffers) (GLsizei n, GLuint *buffers);
typedef void (*PFN_glBindBuffer) (GLenum target, GLuint buffer);
typedef void (*PFN_glBufferData) (GLenum target, GLsizeiptr size, const void *data, GLenum usage);
typedef void (*PFN_glDeleteBuffers) (GLsizei n, const GLuint *buffers);
typedef GLint (*PFN_glGetAttribLocation) (GLuint program, const GLchar *name);
typedef void (*PFN_glEnableVertexAttribArray) (GLuint index);
typedef void (*PFN_glVertexAttribPointer) (GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride, const void *pointer);
typedef void (*PFN_glActiveTexture) (GLenum texture);

static PFN_glCreateShader p_glCreateShader = NULL;
static PFN_glShaderSource p_glShaderSource = NULL;
static PFN_glCompileShader p_glCompileShader = NULL;
static PFN_glGetShaderiv p_glGetShaderiv = NULL;
static PFN_glGetShaderInfoLog p_glGetShaderInfoLog = NULL;
static PFN_glDeleteShader p_glDeleteShader = NULL;
static PFN_glCreateProgram p_glCreateProgram = NULL;
static PFN_glAttachShader p_glAttachShader = NULL;
static PFN_glLinkProgram p_glLinkProgram = NULL;
static PFN_glGetProgramiv p_glGetProgramiv = NULL;
static PFN_glGetProgramInfoLog p_glGetProgramInfoLog = NULL;
static PFN_glDeleteProgram p_glDeleteProgram = NULL;
static PFN_glUseProgram p_glUseProgram = NULL;
static PFN_glGetUniformLocation p_glGetUniformLocation = NULL;
static PFN_glUniform1i p_glUniform1i = NULL;
static PFN_glUniform1ui p_glUniform1ui = NULL;
static PFN_glUniform1f p_glUniform1f = NULL;
static PFN_glGenVertexArrays p_glGenVertexArrays = NULL;
static PFN_glBindVertexArray p_glBindVertexArray = NULL;
static PFN_glDeleteVertexArrays p_glDeleteVertexArrays = NULL;
static PFN_glGenBuffers p_glGenBuffers = NULL;
static PFN_glBindBuffer p_glBindBuffer = NULL;
static PFN_glBufferData p_glBufferData = NULL;
static PFN_glDeleteBuffers p_glDeleteBuffers = NULL;
static PFN_glGetAttribLocation p_glGetAttribLocation = NULL;
static PFN_glEnableVertexAttribArray p_glEnableVertexAttribArray = NULL;
static PFN_glVertexAttribPointer p_glVertexAttribPointer = NULL;
static PFN_glActiveTexture p_glActiveTexture = NULL;

static PFNGLXCREATECONTEXTATTRIBSARBPROC p_glXCreateContextAttribsARB = NULL;
static PFNGLXSWAPINTERVALEXTPROC p_glXSwapIntervalEXT = NULL;
static PFNGLXSWAPINTERVALMESAPROC p_glXSwapIntervalMESA = NULL;
static PFNGLXSWAPINTERVALSGIPROC p_glXSwapIntervalSGI = NULL;

static void* getProc(const char* name) {
    return (void*)glXGetProcAddressARB((const GLubyte*)name);
}

static bool loadGLExtensions(void) {
    p_glCreateShader = (PFN_glCreateShader)getProc("glCreateShader");
    p_glShaderSource = (PFN_glShaderSource)getProc("glShaderSource");
    p_glCompileShader = (PFN_glCompileShader)getProc("glCompileShader");
    p_glGetShaderiv = (PFN_glGetShaderiv)getProc("glGetShaderiv");
    p_glGetShaderInfoLog = (PFN_glGetShaderInfoLog)getProc("glGetShaderInfoLog");
    p_glDeleteShader = (PFN_glDeleteShader)getProc("glDeleteShader");
    p_glCreateProgram = (PFN_glCreateProgram)getProc("glCreateProgram");
    p_glAttachShader = (PFN_glAttachShader)getProc("glAttachShader");
    p_glLinkProgram = (PFN_glLinkProgram)getProc("glLinkProgram");
    p_glGetProgramiv = (PFN_glGetProgramiv)getProc("glGetProgramiv");
    p_glGetProgramInfoLog = (PFN_glGetProgramInfoLog)getProc("glGetProgramInfoLog");
    p_glDeleteProgram = (PFN_glDeleteProgram)getProc("glDeleteProgram");
    p_glUseProgram = (PFN_glUseProgram)getProc("glUseProgram");
    p_glGetUniformLocation = (PFN_glGetUniformLocation)getProc("glGetUniformLocation");
    p_glUniform1i = (PFN_glUniform1i)getProc("glUniform1i");
    p_glUniform1ui = (PFN_glUniform1ui)getProc("glUniform1ui");
    p_glUniform1f = (PFN_glUniform1f)getProc("glUniform1f");
    p_glGenVertexArrays = (PFN_glGenVertexArrays)getProc("glGenVertexArrays");
    p_glBindVertexArray = (PFN_glBindVertexArray)getProc("glBindVertexArray");
    p_glDeleteVertexArrays = (PFN_glDeleteVertexArrays)getProc("glDeleteVertexArrays");
    p_glGenBuffers = (PFN_glGenBuffers)getProc("glGenBuffers");
    p_glBindBuffer = (PFN_glBindBuffer)getProc("glBindBuffer");
    p_glBufferData = (PFN_glBufferData)getProc("glBufferData");
    p_glDeleteBuffers = (PFN_glDeleteBuffers)getProc("glDeleteBuffers");
    p_glGetAttribLocation = (PFN_glGetAttribLocation)getProc("glGetAttribLocation");
    p_glEnableVertexAttribArray = (PFN_glEnableVertexAttribArray)getProc("glEnableVertexAttribArray");
    p_glVertexAttribPointer = (PFN_glVertexAttribPointer)getProc("glVertexAttribPointer");
    p_glActiveTexture = (PFN_glActiveTexture)getProc("glActiveTexture");

    p_glXCreateContextAttribsARB = (PFNGLXCREATECONTEXTATTRIBSARBPROC)getProc("glXCreateContextAttribsARB");
    p_glXSwapIntervalEXT = (PFNGLXSWAPINTERVALEXTPROC)getProc("glXSwapIntervalEXT");
    p_glXSwapIntervalMESA = (PFNGLXSWAPINTERVALMESAPROC)getProc("glXSwapIntervalMESA");
    p_glXSwapIntervalSGI = (PFNGLXSWAPINTERVALSGIPROC)getProc("glXSwapIntervalSGI");

    return (p_glCreateShader && p_glCreateProgram && p_glUseProgram && p_glGenBuffers);
}

// =============================================================================
// STRUCTURE DU FICHIER TEXTURE BINAIRE (.sstvtex)
// =============================================================================
#pragma pack(push, 1)
typedef struct {
    char magic[8];          // "VGASSTV1"
    uint32_t version;       // 1
    uint32_t audio_fs;      // Ex: 48000
    uint32_t total_samples; // Nombre total d'échantillons audio
    uint32_t tex_w;         // Largeur texture (2048)
    uint32_t tex_h;         // Hauteur texture
    double total_duration;  // Durée totale en secondes
    uint32_t data_bytes;    // Taille des données en octets (tex_w * tex_h * 2 * sizeof(float))
    char reserved[32];      // Remplissage futur
} VgaSstvHeader;
#pragma pack(pop)

// =============================================================================
// SHADERS GLSL (DDS + BLU / USB MIXER)
// =============================================================================

static const char* VERTEX_SHADER_SRC =
"#version 330 core\n"
"in vec2 in_position;\n"
"void main() {\n"
"    gl_Position = vec4(in_position, 0.0, 1.0);\n"
"}\n";

static const char* FRAGMENT_SHADER_CW_SRC =
"#version 330 core\n"
"out vec4 FragColor;\n"
"uniform uint u_screen_height;\n"
"uniform uint u_htotal;\n"
"uniform uint u_frame_phase;\n"
"uniform uint u_phase_inc;\n"
"const float TWO_PI = 6.28318530717958647692;\n"
"const float UINT_SCALE = TWO_PI / 4294967296.0;\n"
"void main() {\n"
"    uint y_scan = (u_screen_height - 1u) - uint(floor(gl_FragCoord.y));\n"
"    uint x_scan = uint(floor(gl_FragCoord.x));\n"
"    uint sample_in_frame = (y_scan * u_htotal) + x_scan;\n"
"    uint carrier_phase_uint = u_frame_phase + (sample_in_frame * u_phase_inc);\n"
"    float rf = cos(float(carrier_phase_uint) * UINT_SCALE);\n"
"    FragColor = vec4(0.5 + 0.5 * rf, 0.0, 0.0, 1.0);\n"
"}\n";

static const char* FRAGMENT_SHADER_TONE_SRC =
"#version 330 core\n"
"out vec4 FragColor;\n"
"uniform uint u_screen_height;\n"
"uniform uint u_htotal;\n"
"uniform uint u_frame_phase;\n"
"uniform uint u_phase_inc;\n"
"uniform uint u_tone_frame_phase;\n"
"uniform uint u_tone_phase_inc;\n"
"const float TWO_PI = 6.28318530717958647692;\n"
"const float UINT_SCALE = TWO_PI / 4294967296.0;\n"
"void main() {\n"
"    uint y_scan = (u_screen_height - 1u) - uint(floor(gl_FragCoord.y));\n"
"    uint x_scan = uint(floor(gl_FragCoord.x));\n"
"    uint sample_in_frame = (y_scan * u_htotal) + x_scan;\n"
"    uint carrier_phase_uint = u_frame_phase + (sample_in_frame * u_phase_inc);\n"
"    uint tone_phase_uint = u_tone_frame_phase + (sample_in_frame * u_tone_phase_inc);\n"
"    float rf = cos(float(carrier_phase_uint + tone_phase_uint) * UINT_SCALE);\n"
"    FragColor = vec4(0.5 + 0.5 * rf, 0.0, 0.0, 1.0);\n"
"}\n";

static const char* FRAGMENT_SHADER_SSTV_SRC =
"#version 330 core\n"
"out vec4 FragColor;\n"
"uniform uint u_screen_height;\n"
"uniform uint u_htotal;\n"
"uniform uint u_frame_phase;\n"
"uniform uint u_phase_inc;\n"
"uniform sampler2D u_iq_texture;\n"
"uniform uint u_audio_frame_base_int;\n"
"uniform float u_audio_frame_base_frac;\n"
"uniform float u_audio_advance_per_sample;\n"
"uniform uint u_total_audio_samples;\n"
"const float TWO_PI = 6.28318530717958647692;\n"
"const float UINT_SCALE = TWO_PI / 4294967296.0;\n"
"void main() {\n"
"    uint y_scan = (u_screen_height - 1u) - uint(floor(gl_FragCoord.y));\n"
"    uint x_scan = uint(floor(gl_FragCoord.x));\n"
"    uint sample_in_frame = (y_scan * u_htotal) + x_scan;\n"
"    uint carrier_phase_uint = u_frame_phase + (sample_in_frame * u_phase_inc);\n"
"    float carrier_phase = float(carrier_phase_uint) * UINT_SCALE;\n"
"    float advance = u_audio_frame_base_frac + (float(sample_in_frame) * u_audio_advance_per_sample);\n"
"    uint advance_int = uint(advance);\n"
"    float frac = advance - float(advance_int);\n"
"    uint total_sample_int = u_audio_frame_base_int + advance_int;\n"
"    if (total_sample_int >= u_total_audio_samples) {\n"
"        FragColor = vec4(0.5, 0.0, 0.0, 1.0);\n"
"        return;\n"
"    }\n"
"    int s0_x = int(total_sample_int & 2047u);\n"
"    int s0_y = int(total_sample_int >> 11);\n"
"    vec2 s0 = texelFetch(u_iq_texture, ivec2(s0_x, s0_y), 0).rg;\n"
"    uint next_sample_int = min(total_sample_int + 1u, u_total_audio_samples - 1u);\n"
"    int s1_x = int(next_sample_int & 2047u);\n"
"    int s1_y = int(next_sample_int >> 11);\n"
"    vec2 s1 = texelFetch(u_iq_texture, ivec2(s1_x, s1_y), 0).rg;\n"
"    vec2 iq = mix(s0, s1, frac);\n"
"    float rf = (iq.r * cos(carrier_phase)) - (iq.g * sin(carrier_phase));\n"
"    float dac = 0.5 + 0.5 * rf;\n"
"    float seed = dot(gl_FragCoord.xy, vec2(12.9898, 78.233)) + float(u_frame_phase % 10000u) * 0.1337;\n"
"    float dither = fract(sin(seed) * 43758.5453) - 0.5;\n"
"    dac += dither / 255.0;\n"
"    FragColor = vec4(dac, 0.0, 0.0, 1.0);\n"
"}\n";

// =============================================================================
// COMPILATION SHADERS
// =============================================================================

static GLuint compileShader(GLenum type, const char* src) {
    GLuint shader = p_glCreateShader(type);
    p_glShaderSource(shader, 1, &src, NULL);
    p_glCompileShader(shader);
    GLint success;
    p_glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        char infoLog[1024];
        p_glGetShaderInfoLog(shader, sizeof(infoLog), NULL, infoLog);
        fprintf(stderr, "[-] Erreur compilation shader : %s\n", infoLog);
        exit(1);
    }
    return shader;
}

static GLuint createProgram(const char* vertSrc, const char* fragSrc) {
    GLuint vs = compileShader(GL_VERTEX_SHADER, vertSrc);
    GLuint fs = compileShader(GL_FRAGMENT_SHADER, fragSrc);
    GLuint prog = p_glCreateProgram();
    p_glAttachShader(prog, vs);
    p_glAttachShader(prog, fs);
    p_glLinkProgram(prog);
    GLint success;
    p_glGetProgramiv(prog, GL_LINK_STATUS, &success);
    if (!success) {
        char infoLog[1024];
        p_glGetProgramInfoLog(prog, sizeof(infoLog), NULL, infoLog);
        fprintf(stderr, "[-] Erreur linkage program : %s\n", infoLog);
        exit(1);
    }
    p_glDeleteShader(vs);
    p_glDeleteShader(fs);
    return prog;
}

// =============================================================================
// DÉTECTION TIMINGS D'AFFICHAGE XRANDR
// =============================================================================

static inline uint32_t parseU32(const char* s) {
    uint32_t v = 0;
    while (*s >= '0' && *s <= '9') {
        v = v * 10 + (uint32_t)(*s - '0');
        s++;
    }
    return v;
}

typedef struct {
    bool valid;
    double pclk;
    uint32_t width;
    uint32_t height;
    uint32_t htotal;
    uint32_t vtotal;
} DisplayTimings;

static DisplayTimings detectActiveDisplayTimings(void) {
    DisplayTimings dt = { false, 148.5e6, 1920, 1080, 2200, 1125 };
    FILE* fp = popen("xrandr --verbose 2>/dev/null", "r");
    if (!fp) return dt;

    char line[1024];
    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, "*current") != NULL) {
            char* token = strtok(line, " \t\r\n");
            while (token) {
                size_t len = strlen(token);
                if (len > 3 && strcmp(token + len - 3, "MHz") == 0) {
                    char numBuf[64];
                    strncpy(numBuf, token, len - 3);
                    numBuf[len - 3] = '\0';
                    dt.pclk = atof(numBuf) * 1e6;
                }
                token = strtok(NULL, " \t\r\n");
            }
            if (fgets(line, sizeof(line), fp) && strstr(line, "total")) {
                char* htok = strtok(line, " \t\r\n");
                while (htok) {
                    if (strcmp(htok, "width") == 0) {
                        htok = strtok(NULL, " \t\r\n");
                        if (htok) dt.width = parseU32(htok);
                    } else if (strcmp(htok, "total") == 0) {
                        htok = strtok(NULL, " \t\r\n");
                        if (htok) dt.htotal = parseU32(htok);
                    }
                    htok = strtok(NULL, " \t\r\n");
                }
            }
            if (fgets(line, sizeof(line), fp) && strstr(line, "total")) {
                char* vtok = strtok(line, " \t\r\n");
                while (vtok) {
                    if (strcmp(vtok, "height") == 0) {
                        vtok = strtok(NULL, " \t\r\n");
                        if (vtok) dt.height = parseU32(vtok);
                    } else if (strcmp(vtok, "total") == 0) {
                        vtok = strtok(NULL, " \t\r\n");
                        if (vtok) dt.vtotal = parseU32(vtok);
                    }
                    vtok = strtok(NULL, " \t\r\n");
                }
            }
            if (dt.pclk > 0 && dt.htotal > 0 && dt.vtotal > 0) {
                dt.valid = true;
                break;
            }
        }
    }
    pclose(fp);
    return dt;
}

// Thread de progression
typedef struct {
    volatile uint64_t current_frame;
    volatile bool stop;
    uint32_t samples_per_frame;
    double pixelClock;
    double duration;
} ProgressCtx;

static void* progressWorker(void* arg) {
    ProgressCtx* ctx = (ProgressCtx*)arg;
    while (!ctx->stop) {
        uint64_t idx = ctx->current_frame;
        double t_el = ((double)idx * ctx->samples_per_frame) / ctx->pixelClock;
        double pct = (t_el / ctx->duration) * 100.0;
        if (pct > 100.0) pct = 100.0;
        printf("\r⏳ Progression : [%5.1f%%] - %5.1fs / %5.1fs (Frame #%lu)",
               pct, t_el, ctx->duration, (unsigned long)idx);
        fflush(stdout);
        struct timespec ts = { 1, 0 };
        nanosleep(&ts, NULL);
    }
    return NULL;
}

static inline double getMonotonicSeconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

// =============================================================================
// MAIN
// =============================================================================

int main(int argc, char** argv) {
    int mode = 2; // 0 = CW, 1 = TONE, 2 = SSTV
    const char* inputTexturePath = NULL;
    double carrierFreq = 14.230e6;
    double toneFreq = 1900.0;
    double pixelClock = 0.0;
    uint32_t screenWidth = 0;
    uint32_t screenHeight = 0;
    uint32_t htotal = 0;
    uint32_t vtotal = 0;
    double duration = -1.0;
    bool fullscreen = false;
    bool realtimePrio = false;

    for (int i = 1; i < argc; ++i) {
        const char* arg = argv[i];
        if (strcmp(arg, "--cw") == 0) {
            mode = 0;
        } else if (strcmp(arg, "--tone") == 0) {
            mode = 1;
            if (i + 1 < argc && argv[i + 1][0] != '-') toneFreq = atof(argv[++i]);
        } else if (strcmp(arg, "-f") == 0 || strcmp(arg, "--freq") == 0) {
            if (i + 1 < argc) carrierFreq = atof(argv[++i]);
        } else if (strcmp(arg, "-i") == 0 || strcmp(arg, "--input") == 0 || strcmp(arg, "--texture") == 0) {
            if (i + 1 < argc) inputTexturePath = argv[++i];
        } else if (strcmp(arg, "--pclk") == 0) {
            if (i + 1 < argc) pixelClock = atof(argv[++i]);
        } else if (strcmp(arg, "--width") == 0) {
            if (i + 1 < argc) screenWidth = parseU32(argv[++i]);
        } else if (strcmp(arg, "--height") == 0) {
            if (i + 1 < argc) screenHeight = parseU32(argv[++i]);
        } else if (strcmp(arg, "--htotal") == 0) {
            if (i + 1 < argc) htotal = parseU32(argv[++i]);
        } else if (strcmp(arg, "--vtotal") == 0) {
            if (i + 1 < argc) vtotal = parseU32(argv[++i]);
        } else if (strcmp(arg, "-d") == 0 || strcmp(arg, "--duration") == 0) {
            if (i + 1 < argc) duration = atof(argv[++i]);
        } else if (strcmp(arg, "--fullscreen") == 0) {
            fullscreen = true;
        } else if (strcmp(arg, "-r") == 0 || strcmp(arg, "--realtime") == 0) {
            realtimePrio = true;
        } else if (strcmp(arg, "-h") == 0 || strcmp(arg, "--help") == 0) {
            printf("Usage: %s [options]\n"
                   "Options:\n"
                   "  -i, --input <file.sstvtex>  Texture I/Q pré-générée pour SSTV (Mode 2)\n"
                   "  --cw                       Mode CW (Porteuse pure)\n"
                   "  --tone <freq_hz>           Mode TONE (Tonalité fixe en Hz, ex: 1900)\n"
                   "  -f, --freq <freq_hz>       Fréquence porteuse RF (Défaut: 14.230 MHz)\n"
                   "  --pclk <hz>                Pixel clock en Hz (Défaut: auto-détection xrandr)\n"
                   "  --width <w> / --height <h> Résolution active\n"
                   "  --htotal <h> / --vtotal <v> Timings totaux\n"
                   "  -d, --duration <sec>       Durée d'émission (secondes)\n"
                   "  --fullscreen               Plein écran direct X11\n"
                   "  -r, --realtime             Activer l'ordonnancement temps réel SCHED_FIFO\n", argv[0]);
            return 0;
        } else if (arg[0] != '-' && inputTexturePath == NULL) {
            inputTexturePath = arg;
        }
    }

    // Détection automatique des timings si non spécifiés
    DisplayTimings dt = detectActiveDisplayTimings();
    if (pixelClock <= 0.0) {
        if (dt.valid) {
            pixelClock = dt.pclk;
            if (htotal == 0) htotal = dt.htotal;
            if (vtotal == 0) vtotal = dt.vtotal;
            if (screenWidth == 0) screenWidth = dt.width;
            if (screenHeight == 0) screenHeight = dt.height;
            printf("[+] Timings auto-détectés via xrandr : %.3f MHz (%ux%u, H_total=%u, V_total=%u)\n",
                   pixelClock / 1e6, screenWidth, screenHeight, htotal, vtotal);
        } else {
            pixelClock = 148.5e6;
            if (htotal == 0) htotal = 2200;
            if (vtotal == 0) vtotal = 1125;
            if (screenWidth == 0) screenWidth = 1920;
            if (screenHeight == 0) screenHeight = 1080;
            printf("[!] Fallback timings par défaut : 148.500 MHz (1920x1080, H_total=2200, V_total=1125)\n");
        }
    } else {
        if (htotal == 0) htotal = (pixelClock < 200e6) ? 2200 : 2080;
        if (vtotal == 0) vtotal = (pixelClock < 200e6) ? 1125 : 1144;
        if (screenWidth == 0) screenWidth = 1920;
        if (screenHeight == 0) screenHeight = 1080;
    }

    // Chargement de la texture SSTV si en mode SSTV
    VgaSstvHeader texHeader;
    memset(&texHeader, 0, sizeof(texHeader));
    float* texBuffer = NULL;
    if (mode == 2) {
        if (!inputTexturePath) {
            fprintf(stderr, "[-] Erreur : En mode SSTV, vous devez fournir un fichier de texture binaire (-i / --input <file.sstvtex>).\n"
                            "    Utilisez 'vga_sstv.py <image> --save-texture <file.sstvtex>' pour le générer.\n");
            return 1;
        }
        FILE* fp = fopen(inputTexturePath, "rb");
        if (!fp) {
            fprintf(stderr, "[-] Impossible d'ouvrir le fichier texture : %s\n", inputTexturePath);
            return 1;
        }
        if (fread(&texHeader, sizeof(texHeader), 1, fp) != 1) {
            fprintf(stderr, "[-] Erreur lecture en-tête texture\n");
            fclose(fp);
            return 1;
        }
        if (strncmp(texHeader.magic, "VGASSTV1", 8) != 0) {
            fprintf(stderr, "[-] Format de fichier texture invalide (Magic != VGASSTV1) !\n");
            fclose(fp);
            return 1;
        }
        size_t totalFloats = (size_t)texHeader.tex_w * texHeader.tex_h * 2;
        texBuffer = (float*)malloc(totalFloats * sizeof(float));
        if (!texBuffer) {
            fprintf(stderr, "[-] Échec allocation mémoire texture (%.1f Mo)\n", (double)(totalFloats * sizeof(float)) / (1024.0 * 1024.0));
            fclose(fp);
            return 1;
        }
        if (fread(texBuffer, sizeof(float), totalFloats, fp) != totalFloats) {
            fprintf(stderr, "[-] Erreur de lecture des données de texture !\n");
            free(texBuffer);
            fclose(fp);
            return 1;
        }
        fclose(fp);
        printf("[+] Texture SSTV chargée : %ux%u (%u éch., %.2f s)\n",
               texHeader.tex_w, texHeader.tex_h, texHeader.total_samples, texHeader.total_duration);

        if (duration <= 0.0) {
            duration = texHeader.total_duration;
        } else if (duration > texHeader.total_duration) {
            duration = texHeader.total_duration;
        }
    } else {
        if (duration <= 0.0) duration = 30.0;
    }

    // Priorité temps réel si demandée
    if (realtimePrio) {
        struct sched_param param;
        memset(&param, 0, sizeof(param));
        param.sched_priority = 80;
        if (sched_setscheduler(0, SCHED_FIFO, &param) == 0) {
            printf("[+] Ordonnancement temps réel SCHED_FIFO activé (priorité 80) !\n");
        } else {
            fprintf(stderr, "[!] Avertissement : Impossible d'activer SCHED_FIFO (permissions root requises ou cap_sys_nice).\n");
        }
    }

    const char* modeNames[] = {"PORTEUSE PURE (CW)", "TONALITÉ FIXE", "SSTV MARTIN 1 (C X11/GLX)"};
    printf("\n======================================================================\n"
           "📻 ÉMETTEUR SDR GPU RAMDAC C (AUTONOME X11/GLX) - MODE : %s\n"
           "======================================================================\n"
           "[*] Fréquence porteuse RF : %.6f MHz\n"
           "[*] Pixel Clock           : %.3f MHz\n"
           "[*] Timings d'affichage   : %ux%u (H_total: %u, V_total: %u)\n"
           "[*] Sortie physique       : Broche 1 VGA (Rouge) + Broche 6 (Masse)\n"
           "======================================================================\n",
           modeNames[mode], carrierFreq / 1e6, pixelClock / 1e6, screenWidth, screenHeight, htotal, vtotal);

    const char* displayName = getenv("DISPLAY");
    if (!displayName) displayName = ":0";

    Display* dpy = XOpenDisplay(displayName);
    if (!dpy) {
        fprintf(stderr, "[-] Impossible de se connecter au serveur X11 sur %s\n", displayName);
        if (texBuffer) free(texBuffer);
        return 1;
    }

    static int visual_attribs[] = {
        GLX_X_RENDERABLE, True,
        GLX_DRAWABLE_TYPE, GLX_WINDOW_BIT,
        GLX_RENDER_TYPE, GLX_RGBA_BIT,
        GLX_X_VISUAL_TYPE, GLX_TRUE_COLOR,
        GLX_RED_SIZE, 8,
        GLX_GREEN_SIZE, 8,
        GLX_BLUE_SIZE, 8,
        GLX_DOUBLEBUFFER, True,
        None
    };

    int fbcount = 0;
    GLXFBConfig* fbc = glXChooseFBConfig(dpy, DefaultScreen(dpy), visual_attribs, &fbcount);
    if (!fbc || fbcount <= 0) {
        fprintf(stderr, "[-] Impossible de trouver une configuration FBConfig GLX compatible.\n");
        XCloseDisplay(dpy);
        if (texBuffer) free(texBuffer);
        return 1;
    }

    XVisualInfo* vi = glXGetVisualFromFBConfig(dpy, fbc[0]);
    if (!vi) {
        fprintf(stderr, "[-] Impossible d'obtenir le visualinfo X11.\n");
        XCloseDisplay(dpy);
        if (texBuffer) free(texBuffer);
        return 1;
    }

    XSetWindowAttributes swa;
    swa.colormap = XCreateColormap(dpy, RootWindow(dpy, vi->screen), vi->visual, AllocNone);
    swa.border_pixel = 0;
    swa.event_mask = StructureNotifyMask | KeyPressMask;

    Window win = XCreateWindow(
        dpy, RootWindow(dpy, vi->screen),
        0, 0, screenWidth, screenHeight, 0,
        vi->depth, InputOutput, vi->visual,
        CWBorderPixel | CWColormap | CWEventMask, &swa
    );

    if (!win) {
        fprintf(stderr, "[-] Échec de création de la fenêtre X11.\n");
        XCloseDisplay(dpy);
        if (texBuffer) free(texBuffer);
        return 1;
    }

    XStoreName(dpy, win, "VGA SDR Transmitter (Pure C / GLX)");

    if (fullscreen) {
        Atom wm_state = XInternAtom(dpy, "_NET_WM_STATE", False);
        Atom fullscreen_atom = XInternAtom(dpy, "_NET_WM_STATE_FULLSCREEN", False);
        XChangeProperty(dpy, win, wm_state, 4, 32, PropModeReplace, (unsigned char*)&fullscreen_atom, 1);
    }

    XMapRaised(dpy, win);
    XFlush(dpy);

    if (!loadGLExtensions()) {
        fprintf(stderr, "[-] Échec de chargement des fonctions OpenGL.\n");
        XDestroyWindow(dpy, win);
        XCloseDisplay(dpy);
        if (texBuffer) free(texBuffer);
        return 1;
    }

    GLXContext glCtx = NULL;
    if (p_glXCreateContextAttribsARB) {
        int context_attribs[] = {
            GLX_CONTEXT_MAJOR_VERSION_ARB, 3,
            GLX_CONTEXT_MINOR_VERSION_ARB, 3,
            GLX_CONTEXT_PROFILE_MASK_ARB, GLX_CONTEXT_CORE_PROFILE_BIT_ARB,
            None
        };
        glCtx = p_glXCreateContextAttribsARB(dpy, fbc[0], NULL, True, context_attribs);
    }
    if (!glCtx) {
        glCtx = glXCreateContext(dpy, vi, NULL, True);
    }
    if (!glCtx) {
        fprintf(stderr, "[-] Échec de création du contexte GLX.\n");
        XDestroyWindow(dpy, win);
        XCloseDisplay(dpy);
        if (texBuffer) free(texBuffer);
        return 1;
    }

    glXMakeCurrent(dpy, win, glCtx);

    if (p_glXSwapIntervalEXT) {
        p_glXSwapIntervalEXT(dpy, win, 1);
    } else if (p_glXSwapIntervalMESA) {
        p_glXSwapIntervalMESA(1);
    } else if (p_glXSwapIntervalSGI) {
        p_glXSwapIntervalSGI(1);
    }

    printf("[+] GPU Actif : %s\n", (const char*)glGetString(GL_RENDERER));
    printf("[+] Version OpenGL : %s\n", (const char*)glGetString(GL_VERSION));

    GLuint prog = 0;
    if (mode == 0) prog = createProgram(VERTEX_SHADER_SRC, FRAGMENT_SHADER_CW_SRC);
    else if (mode == 1) prog = createProgram(VERTEX_SHADER_SRC, FRAGMENT_SHADER_TONE_SRC);
    else prog = createProgram(VERTEX_SHADER_SRC, FRAGMENT_SHADER_SSTV_SRC);

    p_glUseProgram(prog);

    GLint loc_screen_height = p_glGetUniformLocation(prog, "u_screen_height");
    GLint loc_htotal = p_glGetUniformLocation(prog, "u_htotal");
    GLint loc_frame_phase = p_glGetUniformLocation(prog, "u_frame_phase");
    GLint loc_phase_inc = p_glGetUniformLocation(prog, "u_phase_inc");

    uint32_t samples_per_frame = htotal * vtotal;
    if (loc_screen_height >= 0) p_glUniform1ui(loc_screen_height, screenHeight);
    if (loc_htotal >= 0) p_glUniform1ui(loc_htotal, htotal);

    uint32_t phase_inc = (uint32_t)((uint64_t)round(4294967296.0 * (carrierFreq / pixelClock)) % 4294967296ULL);
    if (loc_phase_inc >= 0) p_glUniform1ui(loc_phase_inc, phase_inc);

    GLint loc_tone_frame_phase = -1;
    uint32_t tone_phase_inc = 0;
    if (mode == 1) {
        GLint loc_tone_phase_inc = p_glGetUniformLocation(prog, "u_tone_phase_inc");
        loc_tone_frame_phase = p_glGetUniformLocation(prog, "u_tone_frame_phase");
        tone_phase_inc = (uint32_t)((uint64_t)round(4294967296.0 * (toneFreq / pixelClock)) % 4294967296ULL);
        if (loc_tone_phase_inc >= 0) p_glUniform1ui(loc_tone_phase_inc, tone_phase_inc);
    }

    GLuint texID = 0;
    GLint loc_audio_frame_base_int = -1;
    GLint loc_audio_frame_base_frac = -1;
    uint32_t audio_fs = 48000;
    if (mode == 2) {
        audio_fs = texHeader.audio_fs;
        GLint loc_iq_texture = p_glGetUniformLocation(prog, "u_iq_texture");
        loc_audio_frame_base_int = p_glGetUniformLocation(prog, "u_audio_frame_base_int");
        loc_audio_frame_base_frac = p_glGetUniformLocation(prog, "u_audio_frame_base_frac");
        GLint loc_audio_advance_per_sample = p_glGetUniformLocation(prog, "u_audio_advance_per_sample");
        GLint loc_total_audio_samples = p_glGetUniformLocation(prog, "u_total_audio_samples");

        glGenTextures(1, &texID);
        if (p_glActiveTexture) p_glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, texID);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RG32F, texHeader.tex_w, texHeader.tex_h, 0, GL_RG, GL_FLOAT, texBuffer);

        if (loc_iq_texture >= 0) p_glUniform1i(loc_iq_texture, 0);
        if (loc_audio_advance_per_sample >= 0) p_glUniform1f(loc_audio_advance_per_sample, (float)(audio_fs / pixelClock));
        if (loc_total_audio_samples >= 0) p_glUniform1ui(loc_total_audio_samples, texHeader.total_samples);
    }

    float vertices[] = {
        -1.0f, -1.0f,
         1.0f, -1.0f,
        -1.0f,  1.0f,
        -1.0f,  1.0f,
         1.0f, -1.0f,
         1.0f,  1.0f
    };
    GLuint vao, vbo;
    p_glGenVertexArrays(1, &vao);
    p_glGenBuffers(1, &vbo);
    p_glBindVertexArray(vao);
    p_glBindBuffer(GL_ARRAY_BUFFER, vbo);
    p_glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices, GL_STATIC_DRAW);
    GLint loc_pos = p_glGetAttribLocation(prog, "in_position");
    p_glEnableVertexAttribArray(loc_pos);
    p_glVertexAttribPointer(loc_pos, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), (void*)0);

    printf("\n🚀 ÉMISSION EN COURS (Durée : %.1f s)...\n", duration);
    if (mode == 0) printf("   -> Émission porteuse pure (CW).\n");
    else if (mode == 1) printf("   -> Émission tonalité fixe %.1f Hz.\n", toneFreq);
    else printf("   -> Émission SSTV Martin 1 en cours via C OpenGL pipeline.\n");

    ProgressCtx pctx = { 0, false, samples_per_frame, pixelClock, duration };
    pthread_t pThread;
    pthread_create(&pThread, NULL, progressWorker, &pctx);

    uint64_t frame_idx = 0;
    double startTime = getMonotonicSeconds();
    double lastSwap = startTime;
    uint64_t late_frames = 0;
    bool userQuit = false;

    while (!userQuit) {
        while (XPending(dpy) > 0) {
            XEvent ev;
            XNextEvent(dpy, &ev);
            if (ev.type == KeyPress) {
                KeySym sym = XLookupKeysym(&ev.xkey, 0);
                if (sym == XK_Escape || sym == XK_q) {
                    userQuit = true;
                    printf("\n[!] Arrêt demandé par l'utilisateur (Échap/Q).\n");
                    break;
                }
            } else if (ev.type == DestroyNotify) {
                userQuit = true;
                break;
            }
        }
        if (userQuit) break;

        uint32_t frame_phase = (uint32_t)(((uint64_t)frame_idx * samples_per_frame * phase_inc) % 4294967296ULL);
        if (loc_frame_phase >= 0) p_glUniform1ui(loc_frame_phase, frame_phase);

        if (mode == 1) {
            uint32_t tone_frame_phase = (uint32_t)(((uint64_t)frame_idx * samples_per_frame * tone_phase_inc) % 4294967296ULL);
            if (loc_tone_frame_phase >= 0) p_glUniform1ui(loc_tone_frame_phase, tone_frame_phase);
        } else if (mode == 2) {
            double total_audio_sample = ((double)frame_idx * samples_per_frame) * ((double)audio_fs / pixelClock);
            uint32_t base_int = (uint32_t)total_audio_sample;
            float base_frac = (float)(total_audio_sample - (double)base_int);
            if (loc_audio_frame_base_int >= 0) p_glUniform1ui(loc_audio_frame_base_int, base_int);
            if (loc_audio_frame_base_frac >= 0) p_glUniform1f(loc_audio_frame_base_frac, base_frac);
        }

        p_glBindVertexArray(vao);
        glDrawArrays(GL_TRIANGLES, 0, 6);

        glXSwapBuffers(dpy, win);

        double t_elapsed = ((double)frame_idx * samples_per_frame) / pixelClock;
        pctx.current_frame = frame_idx;

        if (t_elapsed >= duration) {
            break;
        }

        double now = getMonotonicSeconds();
        if (frame_idx > 0) {
            double dt_swap = now - lastSwap;
            if (dt_swap > 1.5 * ((double)samples_per_frame / pixelClock)) {
                late_frames++;
            }
        }
        lastSwap = now;

        frame_idx++;
    }

    pctx.stop = true;
    pthread_join(pThread, NULL);

    double endTime = getMonotonicSeconds();
    double wallTime = endTime - startTime;
    double theoTime = ((double)frame_idx * samples_per_frame) / pixelClock;

    printf("\n\n✅ Transmission terminée avec succès !\n");
    if (wallTime > 0.0 && frame_idx > 0) {
        printf("[i] Cadence réelle : %.2f trames/s (théorique %.2f) | temps mural %.2f s vs théorique %.2f s | trames en retard : %lu (%.2f %%)\n",
               frame_idx / wallTime, pixelClock / samples_per_frame, wallTime, theoTime,
               (unsigned long)late_frames, (100.0 * (double)late_frames) / (double)frame_idx);
    }

    if (texID) glDeleteTextures(1, &texID);
    if (texBuffer) free(texBuffer);
    p_glDeleteBuffers(1, &vbo);
    p_glDeleteVertexArrays(1, &vao);
    p_glDeleteProgram(prog);
    glXMakeCurrent(dpy, None, NULL);
    glXDestroyContext(dpy, glCtx);
    XDestroyWindow(dpy, win);
    XCloseDisplay(dpy);

    return 0;
}
