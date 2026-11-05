# PassadaDensa

Benchmark de uma passada direta (*forward pass*) em uma rede neural simples,
implementado em C, Java e Python.

As três versões executam a mesma operação: três camadas densas de tamanho
`h × h`, com ativação ReLU. O projeto mede o tempo de execução e compara um
*checksum* para ajudar a conferir se as implementações produziram resultados
consistentes.

## Requisitos

- Python 3
- GCC
- JDK — inclui `java` e `javac`

O script em Python não depende de NumPy. Para compilar e executar todas as
implementações pelo coletor, os comandos `gcc`, `javac` e `java` precisam estar
disponíveis no terminal.

## Como executar

Na pasta do projeto, rode uma coleta pequena de teste:

```bash
python coletar.py --compilar --blocos 1 --lote 8 --reps 3 --saida piloto.csv
```

Para executar a coleta com os parâmetros padrão:

```bash
python coletar.py --compilar
```

O comando padrão usa 5 blocos, lote 64 e 7 repetições. A coleta pode levar
mais tempo, dependendo do computador.

Para conferir um CSV existente:

```bash
python coletar.py --verificar resultados.csv
```

### Executar uma implementação individualmente

Exemplo com Python:

```bash
python passada.py 64 8 3 2
```

Os argumentos são:

```text
<h> <lote> <repetições> <aquecimento>
```

Também é possível informar um CSV para registrar o resultado:

```bash
python passada.py 64 8 3 2 piloto.csv
```

## Resultados

As execuções podem ser gravadas em arquivos CSV. O coletor também registra
informações sobre o ambiente de execução em um arquivo `*_ambiente.txt`.

O CSV inclui o bloco e a ordem da execução, a linguagem, os parâmetros do teste,
o tempo medido e o *checksum*.

## Observações

- Os tempos dependem do hardware, do sistema operacional, das versões dos
  compiladores e de outros processos em execução.
- Para comparar resultados, execute os testes no mesmo computador e mantenha
  os parâmetros registrados.
- A compilação em C usa opções para evitar reordenações de operações de ponto
  flutuante que podem alterar o *checksum*.
