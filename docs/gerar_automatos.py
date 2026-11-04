#!/usr/bin/env python3
"""Gera os arquivos do JFLAP (.jff) e os diagramas (.png) de docs/automatos/
a partir das MESMAS tabelas de transição usadas pelo validador.py.

Assim os diagramas nunca ficam diferentes do código: depois de mudar um AFD,
basta rodar de novo:

    python docs/gerar_automatos.py

O .jff só usa a biblioteca padrão. O .png precisa do matplotlib
(pip install matplotlib); sem ele, só os .jff são gerados.
"""

import sys
from math import cos, radians, sin
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "docs" / "automatos"
sys.path.insert(0, str(RAIZ))

import validador as v  # noqa: E402


def rotulo_token(simbolo):
    if simbolo == v.TEXT:
        return "texto"
    tipo, nome = simbolo
    return f"<{nome}>" if tipo == v.OPEN else f"</{nome}>"


def posicoes_trie(afd, palavras, x0=60, dx=90):
    """Uma palavra por linha: cada estado fica na coluna da sua profundidade."""
    pos = {str(afd["inicial"]): (x0, 200)}
    alturas = range(80, 80 + 240 * len(palavras), 240)
    for palavra, y in zip(palavras, alturas):
        estado = afd["inicial"]
        for k, c in enumerate(palavra, start=1):
            estado = afd["delta"][(estado, c)]
            pos.setdefault(str(estado), (x0 + 90 + dx * (k - 1), y))
    return pos


# Cada autômato: AFD do código, símbolo usado no JFLAP para cada símbolo
# de Σ, rótulo do símbolo no desenho e posição (x, y) de cada estado.
AUTOMATOS = [
    {
        "nome": "afd_estrutura",
        "titulo": "AFD de estrutura de um bloco <leitura>",
        "afd": {"delta": v.TRANSICOES_ESTRUTURA, "inicial": "q0",
                "aceitacao": v.ACEITACAO_ESTRUTURA},
        "jff": {(v.OPEN, "leitura"): "L", (v.CLOSE, "leitura"): "l",
                (v.OPEN, "sensor"): "S", (v.CLOSE, "sensor"): "s",
                (v.OPEN, "valor"): "V", (v.CLOSE, "valor"): "v",
                (v.OPEN, "unidade"): "U", (v.CLOSE, "unidade"): "u",
                v.TEXT: "t"},
        "rotulo": rotulo_token,
        "posicoes": {f"q{k}": (60 + 125 * k, 80 if k in (3, 6, 9) else 200)
                     for k in range(12)},
    },
    {
        "nome": "afd_sensor",
        "titulo": "AFD sensor (l = letra, d = dígito ou _)",
        "afd": v.AFD_SENSOR,
        "jff": {"L": "l", "D": "d"},
        "rotulo": {"L": "l", "D": "d"}.get,
        "posicoes": {**{str(k): (60 + 110 * k, 80) for k in range(8)},
                     **{f"{k}L": (60 + 110 * k, 260) for k in range(1, 8)}},
    },
    {
        "nome": "afd_valor",
        "titulo": "AFD valor (até 2 casas decimais, mínimo 0.01)",
        "afd": v.AFD_VALOR,
        "jff": {"Z": "z", "NZ": "n", "P": "p"},
        "rotulo": {"Z": "0", "NZ": "1-9", "P": "."}.get,
        "posicoes": {"INI": (60, 200), "INT_Z": (200, 90),
                     "PONTO_Z": (390, 90), "DEC1_Z": (580, 90),
                     "DEC2_Z": (770, 90), "INT": (300, 320),
                     "PONTO": (470, 320), "DEC1": (630, 320),
                     "DEC2": (790, 320)},
        "lacos_abaixo": {"INT"},
    },
    {
        "nome": "afd_unidade",
        "titulo": "AFD unidade {CELSIUS, PERCENTUAL}",
        "afd": v.AFD_UNIDADE,
        "jff": {},                              # os próprios caracteres
        "rotulo": str,
        "posicoes": posicoes_trie(v.AFD_UNIDADE, ["CELSIUS", "PERCENTUAL"]),
    },
]


def arestas(spec):
    """Agrupa as transições por (origem, destino), juntando os símbolos."""
    grupos = {}
    for (origem, simbolo), destino in spec["afd"]["delta"].items():
        grupos.setdefault((str(origem), str(destino)), []).append(simbolo)
    return grupos


def gerar_jff(spec):
    estados = list(spec["posicoes"])
    ids = {nome: i for i, nome in enumerate(estados)}
    afd = spec["afd"]
    linhas = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
              '<structure><type>fa</type><automaton>']
    for nome in estados:
        x, y = spec["posicoes"][nome]
        marcas = ("<initial/>" if nome == str(afd["inicial"]) else "") + \
                 ("<final/>" if nome in {str(e) for e in afd["aceitacao"]} else "")
        linhas.append(f'<state id="{ids[nome]}" name="{escape(nome)}">'
                      f'<x>{x}</x><y>{y}</y>{marcas}</state>')
    for (origem, simbolo), destino in afd["delta"].items():
        lido = spec["jff"].get(simbolo, simbolo)
        linhas.append(f"<transition><from>{ids[str(origem)]}</from>"
                      f"<to>{ids[str(destino)]}</to>"
                      f"<read>{escape(lido)}</read></transition>")
    linhas.append("</automaton></structure>")
    (PASTA / f"{spec['nome']}.jff").write_text("\n".join(linhas) + "\n",
                                               encoding="utf-8")


def gerar_png(spec, plt, patches, Path):
    pos = {n: (x, -y) for n, (x, y) in spec["posicoes"].items()}
    raio = {n: max(22, 4.3 * len(n) + 8) for n in pos}
    afd = spec["afd"]
    finais = {str(e) for e in afd["aceitacao"]}
    abaixo = spec.get("lacos_abaixo", set())

    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    x0, x1 = min(xs) - 70, max(xs) + 60
    y0, y1 = min(ys) - 90, max(ys) + 120
    fig = plt.figure(figsize=((x1 - x0) / 100, (y1 - y0) / 100))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text((x0 + x1) / 2, y1 - 22, spec["titulo"], ha="center",
            va="center", fontsize=13)

    def seta(a, b):
        ax.add_patch(patches.FancyArrowPatch(
            a, b, arrowstyle="-|>", mutation_scale=12, lw=1.1,
            color="black", shrinkA=0, shrinkB=0))

    def laco(x, y, r, sinal):
        """Laço (transição de um estado para ele mesmo) acima ou abaixo."""
        def ponto(graus, dist):
            return (x + dist * cos(radians(graus)),
                    y + sinal * dist * sin(radians(graus)))
        caminho = Path([ponto(115, r), ponto(110, r + 45),
                        ponto(70, r + 45), ponto(65, r)],
                       [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
        ax.add_patch(patches.FancyArrowPatch(
            path=caminho, arrowstyle="-|>", mutation_scale=12, lw=1.1,
            color="black"))

    def rotulo(x, y, texto):
        ax.text(x, y, texto, ha="center", va="center", fontsize=9,
                bbox={"fc": "white", "ec": "none", "pad": 1})

    for (origem, destino), simbolos in arestas(spec).items():
        texto = ", ".join(spec["rotulo"](s) for s in simbolos)
        (xa, ya), (xb, yb) = pos[origem], pos[destino]
        ra, rb = raio[origem], raio[destino]
        if origem == destino:
            sinal = -1 if origem in abaixo else 1
            laco(xa, ya, ra, sinal)
            rotulo(xa, ya + sinal * (ra + 46), texto)
            continue
        dx, dy = xb - xa, yb - ya
        d = (dx * dx + dy * dy) ** 0.5
        ux, uy = dx / d, dy / d
        seta((xa + ux * ra, ya + uy * ra), (xb - ux * rb, yb - uy * rb))
        # rótulo no meio da aresta, deslocado para cima dela
        nx, ny = (-uy, ux) if ux >= 0 else (uy, -ux)
        rotulo((xa + xb) / 2 + nx * 11, (ya + yb) / 2 + ny * 11, texto)

    for nome, (x, y) in pos.items():
        ax.add_patch(patches.Circle((x, y), raio[nome], fc="white",
                                    ec="black", lw=1.1, zorder=3))
        if nome in finais:
            ax.add_patch(patches.Circle((x, y), raio[nome] - 4, fc="none",
                                        ec="black", lw=1.1, zorder=4))
        ax.text(x, y, nome, ha="center", va="center", fontsize=10, zorder=5)

    xi, yi = pos[str(afd["inicial"])]
    ri = raio[str(afd["inicial"])]
    seta((xi - ri - 35, yi), (xi - ri, yi))
    ax.plot([xi - ri - 35], [yi], "k.", markersize=4)

    fig.savefig(PASTA / f"{spec['nome']}.png", dpi=150, facecolor="white")
    plt.close(fig)


def main():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.path import Path as MplPath
    except ImportError:
        plt = None
        print("matplotlib não instalado: gerando só os arquivos .jff.")

    for spec in AUTOMATOS:
        gerar_jff(spec)
        if plt:
            gerar_png(spec, plt, patches, MplPath)
        print(f"gerado docs/automatos/{spec['nome']}")


if __name__ == "__main__":
    main()
