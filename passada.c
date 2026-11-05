/*
 * Passada direta (forward pass) de 3 camadas densas h x h com ReLU.
 *
 * Compilar (Linux/macOS/MSYS2/MinGW):
 *     gcc -O2 -ffp-contract=off -o passada passada.c -lm
 *
 * Uso:   passada <h> <lote> <reps> <aquecimento> [arquivo.csv bloco ordem]
 * Saida: "<mediana_em_segundos> <checksum>"  (sempre impressa na tela)
 *
 * Se arquivo.csv for informado, tambem acrescenta uma linha a ele (criando o
 * cabecalho se o arquivo ainda nao existir). 'bloco' e 'ordem' sao opcionais
 * (padrao 0) e servem para identificar a execucao dentro do experimento.
 *
 * IMPORTANTE: nao use -ffast-math nem -Ofast. Eles reordenam as somas em
 * ponto flutuante e mudam o checksum em relacao ao Java e ao Python.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

#define CAMADAS 3

#if defined(__GNUC__)
#define NAO_INLINE __attribute__((noinline))
#else
#define NAO_INLINE
#endif

static double agora(void) {
#ifdef _WIN32
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart / (double)f.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
#endif
}

/* Gerador congruencial linear: identico nas tres linguagens. */
static uint64_t estado;
static double aleatorio(void) {
    estado = (estado * 1103515245ULL + 12345ULL) & 0x7FFFFFFFULL;
    return (double)estado / 2147483647.0 - 0.5;
}

/* W: CAMADAS matrizes h x h, em ordem camada -> linha -> coluna. */
NAO_INLINE
static void passada(const double *W, const double *entradas, double *saidas,
                    double *buf1, double *buf2, int h, int lote) {
    for (int s = 0; s < lote; s++) {
        double *x = buf1, *y = buf2;
        for (int i = 0; i < h; i++) x[i] = entradas[(size_t)s * h + i];
        for (int c = 0; c < CAMADAS; c++) {
            const double *Wc = W + (size_t)c * h * h;
            for (int j = 0; j < h; j++) {
                const double *linha = Wc + (size_t)j * h;
                double acc = 0.0;
                for (int i = 0; i < h; i++) acc += linha[i] * x[i];
                y[j] = acc > 0.0 ? acc : 0.0; /* ReLU */
            }
            double *t = x; x = y; y = t;
        }
        for (int j = 0; j < h; j++) saidas[(size_t)s * h + j] = x[j];
    }
}

static void gravar_csv(const char *caminho, int bloco, int ordem, int h,
                       int lote, int reps, int aquec, double tempo,
                       double checksum) {
    FILE *f = fopen(caminho, "a");
    if (!f) {
        fprintf(stderr, "nao foi possivel abrir %s\n", caminho);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    if (ftell(f) == 0)
        fprintf(f, "bloco,ordem,linguagem,h,lote,reps,aquecimento,tempo_s,checksum\n");
    fprintf(f, "%d,%d,C,%d,%d,%d,%d,%.9f,%.17g\n", bloco, ordem, h, lote, reps,
            aquec, tempo, checksum);
    fclose(f);
}

static int cmp(const void *a, const void *b) {
    double da = *(const double *)a, db = *(const double *)b;
    return (da > db) - (da < db);
}

int main(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr, "uso: %s <h> <lote> <reps> <aquecimento> [arquivo.csv bloco ordem]\n", argv[0]);
        return 1;
    }
    int h = atoi(argv[1]), lote = atoi(argv[2]);
    int reps = atoi(argv[3]), aquec = atoi(argv[4]);

    size_t nW = (size_t)CAMADAS * h * h, nE = (size_t)lote * h;
    double *W = malloc(nW * sizeof(double));
    double *entradas = malloc(nE * sizeof(double));
    double *saidas = malloc(nE * sizeof(double));
    double *buf1 = malloc((size_t)h * sizeof(double));
    double *buf2 = malloc((size_t)h * sizeof(double));
    double *tempos = malloc((size_t)reps * sizeof(double));
    if (!W || !entradas || !saidas || !buf1 || !buf2 || !tempos) {
        fprintf(stderr, "falha de alocacao\n");
        return 1;
    }

    estado = 42;
    double escala = 2.0 / sqrt((double)h);
    for (size_t k = 0; k < nW; k++) W[k] = aleatorio() * escala;
    for (size_t k = 0; k < nE; k++) entradas[k] = aleatorio();

    for (int k = 0; k < aquec; k++)
        passada(W, entradas, saidas, buf1, buf2, h, lote);

    for (int r = 0; r < reps; r++) {
        double t0 = agora();
        passada(W, entradas, saidas, buf1, buf2, h, lote);
        tempos[r] = agora() - t0;
    }

    /* checksum fora da medicao: soma sequencial (amostra, neuronio) */
    double checksum = 0.0;
    for (size_t k = 0; k < nE; k++) checksum += saidas[k];

    qsort(tempos, (size_t)reps, sizeof(double), cmp);
    double mediana = (reps % 2) ? tempos[reps / 2]
                                : (tempos[reps / 2 - 1] + tempos[reps / 2]) / 2.0;

    printf("%.9f %.17g\n", mediana, checksum);

    if (argc >= 6) {
        int bloco = (argc >= 7) ? atoi(argv[6]) : 0;
        int ordem = (argc >= 8) ? atoi(argv[7]) : 0;
        gravar_csv(argv[5], bloco, ordem, h, lote, reps, aquec, mediana, checksum);
    }
    return 0;
}
