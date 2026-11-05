"""
Passada direta (forward pass) de 3 camadas densas h x h com ReLU.

Uso:   python passada.py <h> <lote> <reps> <aquecimento> [arquivo.csv bloco ordem]
Saida: "<mediana_em_segundos> <checksum>"  (sempre impressa na tela)

Se arquivo.csv for informado, tambem acrescenta uma linha a ele (criando o
cabecalho se o arquivo ainda nao existir). 'bloco' e 'ordem' sao opcionais
(padrao 0) e servem para identificar a execucao dentro do experimento.

Python puro, sem NumPy. As somas sao feitas com laco explicito (nao use sum()):
a partir do Python 3.12, sum() de floats usa soma compensada e mudaria o
checksum em relacao ao C e ao Java.
"""
import math
import os
import statistics
import sys
import time

CAMADAS = 3


class Gerador:
    """Gerador congruencial linear: identico nas tres linguagens."""

    def __init__(self, semente):
        self.estado = semente

    def proximo(self):
        self.estado = (self.estado * 1103515245 + 12345) & 0x7FFFFFFF
        return self.estado / 2147483647.0 - 0.5


def passada(W, entradas, h):
    saidas = []
    for x in entradas:
        for c in range(CAMADAS):
            y = []
            for linha in W[c]:
                acc = 0.0
                for w, xi in zip(linha, x):
                    acc += w * xi
                y.append(acc if acc > 0.0 else 0.0)  # ReLU
            x = y
        saidas.append(x)
    return saidas


def gravar_csv(caminho, bloco, ordem, h, lote, reps, aquec, tempo, checksum):
    novo = not os.path.exists(caminho) or os.path.getsize(caminho) == 0
    with open(caminho, "a", encoding="utf-8") as f:
        if novo:
            f.write("bloco,ordem,linguagem,h,lote,reps,aquecimento,tempo_s,checksum\n")
        f.write(f"{bloco},{ordem},Python,{h},{lote},{reps},{aquec},"
                f"{tempo:.9f},{checksum!r}\n")


def main():
    if len(sys.argv) < 5:
        sys.exit("uso: python passada.py <h> <lote> <reps> <aquecimento> "
                 "[arquivo.csv bloco ordem]")
    h, lote, reps, aquec = (int(a) for a in sys.argv[1:5])

    g = Gerador(42)
    escala = 2.0 / math.sqrt(float(h))
    # W[camada][linha][coluna], gerado em ordem camada -> linha -> coluna
    W = [[[g.proximo() * escala for _ in range(h)] for _ in range(h)]
         for _ in range(CAMADAS)]
    entradas = [[g.proximo() for _ in range(h)] for _ in range(lote)]

    saidas = None
    for _ in range(aquec):
        saidas = passada(W, entradas, h)

    tempos = []
    for _ in range(reps):
        t0 = time.perf_counter()
        saidas = passada(W, entradas, h)
        tempos.append(time.perf_counter() - t0)

    # checksum fora da medicao: soma sequencial (amostra, neuronio)
    checksum = 0.0
    for s in saidas:
        for v in s:
            checksum += v

    mediana = statistics.median(tempos)
    print(f"{mediana:.9f} {checksum!r}")

    if len(sys.argv) >= 6:
        bloco = int(sys.argv[6]) if len(sys.argv) >= 7 else 0
        ordem = int(sys.argv[7]) if len(sys.argv) >= 8 else 0
        gravar_csv(sys.argv[5], bloco, ordem, h, lote, reps, aquec, mediana, checksum)


if __name__ == "__main__":
    main()
