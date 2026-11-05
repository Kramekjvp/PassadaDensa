/*
 * Passada direta (forward pass) de 3 camadas densas h x h com ReLU.
 *
 * Compilar:  javac Passada.java
 * Uso:       java Passada <h> <lote> <reps> <aquecimento> [arquivo.csv bloco ordem]
 * Saida:     "<mediana_em_segundos> <checksum>"  (sempre impressa na tela)
 *
 * Se arquivo.csv for informado, tambem acrescenta uma linha a ele (criando o
 * cabecalho se o arquivo ainda nao existir). 'bloco' e 'ordem' sao opcionais
 * (padrao 0) e servem para identificar a execucao dentro do experimento.
 */
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.Locale;

public class Passada {
    static final int CAMADAS = 3;

    /* Gerador congruencial linear: identico nas tres linguagens. */
    static long estado;

    static double aleatorio() {
        estado = (estado * 1103515245L + 12345L) & 0x7FFFFFFFL;
        return (double) estado / 2147483647.0 - 0.5;
    }

    /* W[c]: matriz h x h da camada c, em ordem linha -> coluna. */
    static void passada(double[][] W, double[] entradas, double[] saidas,
                        double[] buf1, double[] buf2, int h, int lote) {
        for (int s = 0; s < lote; s++) {
            double[] x = buf1, y = buf2;
            System.arraycopy(entradas, s * h, x, 0, h);
            for (int c = 0; c < CAMADAS; c++) {
                double[] Wc = W[c];
                for (int j = 0; j < h; j++) {
                    int base = j * h;
                    double acc = 0.0;
                    for (int i = 0; i < h; i++) acc += Wc[base + i] * x[i];
                    y[j] = acc > 0.0 ? acc : 0.0; // ReLU
                }
                double[] t = x; x = y; y = t;
            }
            System.arraycopy(x, 0, saidas, s * h, h);
        }
    }

    static void gravarCsv(String caminho, int bloco, int ordem, int h, int lote,
                          int reps, int aquec, double tempo, double checksum)
            throws IOException {
        Path p = Paths.get(caminho);
        String nl = System.lineSeparator();
        StringBuilder sb = new StringBuilder();
        if (!Files.exists(p) || Files.size(p) == 0)
            sb.append("bloco,ordem,linguagem,h,lote,reps,aquecimento,tempo_s,checksum").append(nl);
        sb.append(String.format(Locale.ROOT, "%d,%d,Java,%d,%d,%d,%d,%.9f,",
                bloco, ordem, h, lote, reps, aquec, tempo));
        sb.append(Double.toString(checksum)).append(nl);
        Files.write(p, sb.toString().getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 4) {
            System.err.println("uso: java Passada <h> <lote> <reps> <aquecimento> [arquivo.csv bloco ordem]");
            System.exit(1);
        }
        int h = Integer.parseInt(args[0]);
        int lote = Integer.parseInt(args[1]);
        int reps = Integer.parseInt(args[2]);
        int aquec = Integer.parseInt(args[3]);

        double[][] W = new double[CAMADAS][h * h];
        double[] entradas = new double[lote * h];
        double[] saidas = new double[lote * h];
        double[] buf1 = new double[h], buf2 = new double[h];
        double[] tempos = new double[reps];

        estado = 42;
        double escala = 2.0 / Math.sqrt((double) h);
        for (int c = 0; c < CAMADAS; c++)
            for (int k = 0; k < h * h; k++) W[c][k] = aleatorio() * escala;
        for (int k = 0; k < entradas.length; k++) entradas[k] = aleatorio();

        for (int k = 0; k < aquec; k++)
            passada(W, entradas, saidas, buf1, buf2, h, lote);

        for (int r = 0; r < reps; r++) {
            long t0 = System.nanoTime();
            passada(W, entradas, saidas, buf1, buf2, h, lote);
            tempos[r] = (System.nanoTime() - t0) * 1e-9;
        }

        // checksum fora da medicao: soma sequencial (amostra, neuronio)
        double checksum = 0.0;
        for (int k = 0; k < saidas.length; k++) checksum += saidas[k];

        Arrays.sort(tempos);
        double mediana = (reps % 2 == 1) ? tempos[reps / 2]
                : (tempos[reps / 2 - 1] + tempos[reps / 2]) / 2.0;

        // Double.toString devolve a menor representacao que reconstroi o valor exato
        System.out.println(String.format(Locale.ROOT, "%.9f", mediana) + " " + Double.toString(checksum));

        if (args.length >= 5) {
            int bloco = (args.length >= 6) ? Integer.parseInt(args[5]) : 0;
            int ordem = (args.length >= 7) ? Integer.parseInt(args[6]) : 0;
            gravarCsv(args[4], bloco, ordem, h, lote, reps, aquec, mediana, checksum);
        }
    }
}
