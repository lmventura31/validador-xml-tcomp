#!/usr/bin/env python3
"""Roda o validador em cada arquivo de testes/ e compara a saída com
testes/esperado/<nome>.txt. O código de saída também é conferido: 0 quando
o esperado é sucesso e 1 quando há erros.

Depois roda os testes unitários de testes/test_*.py (AFDs isolados e
conferência dos arquivos .jff com o código).

Uso:
    python rodar_testes.py
"""

import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PASTA_TESTES = RAIZ / "testes"
PASTA_ESPERADO = PASTA_TESTES / "esperado"


def testes_de_arquivo():
    arquivos = sorted(PASTA_TESTES.glob("*.xml"))
    falhas = 0
    for xml in arquivos:
        esperado = (PASTA_ESPERADO / f"{xml.stem}.txt").read_text(
            encoding="utf-8").strip()
        codigo_esperado = 0 if esperado.startswith("Sucesso") else 1
        execucao = subprocess.run(
            [sys.executable, str(RAIZ / "validador.py"), str(xml)],
            capture_output=True, encoding="utf-8",
        )
        resultado = execucao.stdout.strip()
        if resultado == esperado and execucao.returncode == codigo_esperado:
            print(f"OK     {xml.name}")
        else:
            falhas += 1
            print(f"FALHOU {xml.name}")
            print(f"  código de saída: esperado {codigo_esperado}, "
                  f"obtido {execucao.returncode}")
            print("  esperado:\n    " + esperado.replace("\n", "\n    "))
            print("  obtido:\n    " + resultado.replace("\n", "\n    "))

    print(f"\n{len(arquivos) - falhas}/{len(arquivos)} testes de arquivo "
          f"passaram.\n")
    return falhas == 0


def testes_unitarios():
    suite = unittest.defaultTestLoader.discover(str(PASTA_TESTES),
                                                pattern="test_*.py")
    resultado = unittest.TextTestRunner(stream=sys.stdout,
                                        verbosity=1).run(suite)
    return resultado.wasSuccessful()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    arquivos_ok = testes_de_arquivo()
    unitarios_ok = testes_unitarios()
    sys.exit(0 if arquivos_ok and unitarios_ok else 1)


if __name__ == "__main__":
    main()
