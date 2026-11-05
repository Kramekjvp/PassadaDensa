#!/usr/bin/env python3
"""
coletar.py -- Coleta dos tempos do experimento (DBC fatorial 3 x 4).

Substitui o coletar.R. Cada programa (C, Java, Python) mede o proprio tempo e
grava a sua linha no CSV; este script so coordena:
  1. sorteia a ordem das 12 combinacoes (3 linguagens x 4 valores de h)
     dentro de cada bloco;
  2. chama cada programa com bloco e ordem;
  3. confere se as tres linguagens calcularam o mesmo checksum;
  4. retoma de onde parou se for interrompido (rode o mesmo comando de novo).

Uso (na pasta onde estao passada.c, Passada.java e passada.py):
    python coletar.py --compilar                 # compila C e Java e coleta
    python coletar.py                            # 5 blocos, lote 64, 7 repeticoes
    python coletar.py --blocos 1 --lote 8 --reps 3 --saida piloto.csv   # piloto
    python coletar.py --verificar resultados.csv # so confere um CSV existente

Para continuar uma coleta interrompida, rode o MESMO comando (mesma --seed,
--lote e --reps): as combinacoes ja gravadas no CSV sao puladas.
"""
import argparse
import csv
import os
import platform
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
WIN = os.name == "nt"

HS = [64, 128, 256, 512]
# Aquecimento (passadas descartadas antes de medir). A JVM precisa de mais
# passadas para estabilizar; isso nao entra na medicao.
LINGUAGENS = {
    "C": {"cmd": [str(PASTA / ("passada.exe" if WIN else "passada"))],
          "aquecimento": 3},
    "Java": {"cmd": ["java", "-cp", str(PASTA), "Passada"],
             "aquecimento": 30},
    "Python": {"cmd": [sys.executable, str(PASTA / "passada.py")],
               "aquecimento": 2},
}
TOLERANCIA = 1e-9  # diferenca relativa aceita entre checksums


# ---------------------------------------------------------------- utilidades
def compilar():
    print("Compilando C e Java...")
    exe = PASTA / ("passada.exe" if WIN else "passada")
    subprocess.run(["gcc", "-O2", "-ffp-contract=off", "-o", str(exe),
                    str(PASTA / "passada.c"), "-lm"], check=True)
    subprocess.run(["javac", "-d", str(PASTA), str(PASTA / "Passada.java")],
                   check=True)


def checar_programas():
    faltando = []
    if not Path(LINGUAGENS["C"]["cmd"][0]).exists():
        faltando.append("executavel do C (gcc -O2 -ffp-contract=off -o passada passada.c -lm)")
    if not (PASTA / "Passada.class").exists():
        faltando.append("Passada.class (javac Passada.java)")
    if not (PASTA / "passada.py").exists():
        faltando.append("passada.py")
    if faltando:
        sys.exit("Faltam arquivos:\n  - " + "\n  - ".join(faltando)
                 + "\nOu rode com --compilar.")


def ler_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def checksums_divergentes(linhas):
    """Valores de h em que as execucoes nao calcularam o mesmo checksum."""
    por_h = {}
    for l in linhas:
        por_h.setdefault(int(l["h"]), []).append(float(l["checksum"]))
    ruins = []
    for h, valores in sorted(por_h.items()):
        ref = valores[0]
        if any(abs(v - ref) > TOLERANCIA * max(1.0, abs(ref)) for v in valores):
            ruins.append(h)
    return ruins


def verificar(caminho):
    """Confere balanceamento (1 observacao por combinacao e bloco) e checksums."""
    linhas = ler_csv(caminho)
    esperadas = len(LINGUAGENS) * len(HS)
    por_bloco = {}
    for l in linhas:
        por_bloco.setdefault(int(l["bloco"]), []).append((l["linguagem"], int(l["h"])))
    problemas = []
    for b, itens in sorted(por_bloco.items()):
        if len(itens) != len(set(itens)):
            problemas.append(f"bloco {b}: ha combinacao repetida")
        if len(set(itens)) != esperadas:
            problemas.append(f"bloco {b}: {len(set(itens))} de {esperadas} combinacoes")
    for h in checksums_divergentes(linhas):
        problemas.append(f"checksum diverge entre linguagens em h={h}")
    print(f"{len(linhas)} linhas em {len(por_bloco)} bloco(s).")
    if problemas:
        print("PROBLEMAS ENCONTRADOS:")
        for p in problemas:
            print("  -", p)
    else:
        print("OK: dados balanceados e checksums consistentes.")
    return not problemas


def versao(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return ((r.stdout or r.stderr).strip().splitlines() or ["?"])[0]
    except Exception:
        return "indisponivel"


def registrar_ambiente(saida, args):
    linhas = [
        f"Data: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Sistema: {platform.system()} {platform.release()} {platform.machine()}",
        f"Processador: {platform.processor() or 'n/d'}",
        f"Python: {sys.version.split()[0]}",
        f"gcc: {versao(['gcc', '--version'])}",
        f"Java: {versao(['java', '-version'])}",
        f"Parametros: blocos={args.blocos} lote={args.lote} reps={args.reps} seed={args.seed}",
        "",
    ]
    arq = saida.with_name(saida.stem + "_ambiente.txt")
    with open(arq, "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print("\n".join(linhas))


# ------------------------------------------------------------------- coleta
def executar(lang, h, args, saida, bloco, ordem):
    cfg = LINGUAGENS[lang]
    cmd = cfg["cmd"] + [str(h), str(args.lote), str(args.reps),
                        str(cfg["aquecimento"]), str(saida), str(bloco), str(ordem)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"falha em {lang} h={h}:\n{r.stdout}\n{r.stderr}")
    tempo, checksum = (float(x) for x in r.stdout.strip().splitlines()[-1].split())
    return tempo, checksum


def coletar(args):
    saida = Path(args.saida).resolve()
    feitos, referencia = set(), {}

    if saida.exists() and saida.stat().st_size > 0:
        existentes = ler_csv(saida)
        for l in existentes:
            if int(l["lote"]) != args.lote or int(l["reps"]) != args.reps:
                sys.exit(f"{saida.name} foi gerado com outros parametros "
                         f"(lote={l['lote']}, reps={l['reps']}). "
                         "Use outro --saida ou apague o arquivo.")
            if int(l["aquecimento"]) != LINGUAGENS[l["linguagem"]]["aquecimento"]:
                sys.exit(f"{saida.name} foi gerado com outro aquecimento para "
                         f"{l['linguagem']}. Use outro --saida ou apague o arquivo.")
            feitos.add((int(l["bloco"]), l["linguagem"], int(l["h"])))
            referencia.setdefault(int(l["h"]), float(l["checksum"]))
        print(f"Arquivo existente: {len(feitos)} execucoes ja gravadas (serao puladas).\n")

    registrar_ambiente(saida, args)
    combinacoes = [(l, h) for l in LINGUAGENS for h in HS]
    total = len(combinacoes)
    divergencias = 0

    for bloco in range(1, args.blocos + 1):
        # sorteio da ordem: depende so de (seed, bloco), entao e reproduzivel
        ordem_sorteada = combinacoes[:]
        random.Random(f"{args.seed}-{bloco}").shuffle(ordem_sorteada)
        print(f"=== Bloco {bloco}/{args.blocos} ===")
        for ordem, (lang, h) in enumerate(ordem_sorteada, start=1):
            if (bloco, lang, h) in feitos:
                print(f"  [{ordem:2d}/{total}] {lang:<6} h={h:3d}  (ja feito, pulando)")
                continue
            t0 = time.time()
            tempo, checksum = executar(lang, h, args, saida, bloco, ordem)
            ref = referencia.setdefault(h, checksum)
            ok = abs(checksum - ref) <= TOLERANCIA * max(1.0, abs(ref))
            if not ok:
                divergencias += 1
            print(f"  [{ordem:2d}/{total}] {lang:<6} h={h:3d}  {tempo:10.6f} s"
                  f"  ({time.time() - t0:5.1f} s de execucao)"
                  + ("" if ok else "  <-- CHECKSUM DIVERGE"))

    print("\nConferindo o arquivo final...")
    ok = verificar(saida)
    if divergencias:
        print(f"ATENCAO: {divergencias} execucao(oes) com checksum divergente nesta rodada.")
    print(f"\nDados em: {saida}")
    return ok and divergencias == 0


def main():
    ap = argparse.ArgumentParser(description="Coleta dos tempos do experimento DBC 3 x 4")
    ap.add_argument("--blocos", type=int, default=5, help="numero de blocos (sessoes) [5]")
    ap.add_argument("--lote", type=int, default=64, help="amostras por passada [64]")
    ap.add_argument("--reps", type=int, default=7, help="repeticoes internas, use impar [7]")
    ap.add_argument("--saida", default="resultados.csv", help="arquivo CSV [resultados.csv]")
    ap.add_argument("--seed", default="2026", help="semente do sorteio da ordem [2026]")
    ap.add_argument("--compilar", action="store_true", help="compila C e Java antes de coletar")
    ap.add_argument("--verificar", metavar="CSV", help="apenas confere um CSV existente")
    args = ap.parse_args()

    if args.verificar:
        sys.exit(0 if verificar(args.verificar) else 1)

    if args.reps % 2 == 0:
        print("Aviso: reps par; a mediana sera a media dos dois valores centrais.")
    if args.compilar:
        compilar()
    checar_programas()

    try:
        ok = coletar(args)
    except KeyboardInterrupt:
        sys.exit("\nInterrompido. Rode o mesmo comando para continuar de onde parou.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
