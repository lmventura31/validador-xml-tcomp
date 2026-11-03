#!/usr/bin/env python3
"""Roda o validador em cada arquivo de testes/ e compara a saída com
testes/esperado/<nome>.txt.

Uso:
    python rodar_testes.py
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PASTA_TESTES = RAIZ / "testes"
PASTA_ESPERADO = PASTA_TESTES / "esperado"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    arquivos = sorted(PASTA_TESTES.glob("*.xml"))
    falhas = 0
    for xml in arquivos:
        esperado = (PASTA_ESPERADO / f"{xml.stem}.txt").read_text(
            encoding="utf-8").strip()
        resultado = subprocess.run(
            [sys.executable, str(RAIZ / "validador.py"), str(xml)],
            capture_output=True, encoding="utf-8",
        ).stdout.strip()
        if resultado == esperado:
            print(f"OK     {xml.name}")
        else:
            falhas += 1
            print(f"FALHOU {xml.name}")
            print("  esperado:\n    " + esperado.replace("\n", "\n    "))
            print("  obtido:\n    " + resultado.replace("\n", "\n    "))

    print(f"\n{len(arquivos) - falhas}/{len(arquivos)} testes passaram.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
