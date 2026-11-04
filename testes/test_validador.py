"""Testes unitários dos AFDs e do validador.

Complementam os testes de arquivo (testes/*.xml): aqui cada AFD é testado
isoladamente com cadeias de fronteira, e os arquivos .jff de docs/automatos/
são comparados com as tabelas de transição do código.

Rodar:  python rodar_testes.py   (ou: python -m unittest discover -s testes)
"""

import sys
import unittest
import xml.etree.ElementTree as ET  # só para ler os .jff do JFLAP nos testes
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import validador as v  # noqa: E402

LEITURA_OK = ("<leitura><sensor>TEMP_01</sensor><valor>24.5</valor>"
              "<unidade>CELSIUS</unidade></leitura>")


class TestAfdSensor(unittest.TestCase):
    def test_aceita(self):
        for s in ["TEMP_01", "UMID_02", "SENSORA", "temp_01", "A123456",
                  "1_2345X", "_A_____"]:
            with self.subTest(s=s):
                self.assertTrue(v.afd_sensor(s))

    def test_rejeita(self):
        for s in ["", "TEMP_1", "TEMP_001", "1234567", "_______", "TEMP-01",
                  "TEMP 01", "ÁGUA_01", " TEMP_01"]:
            with self.subTest(s=s):
                self.assertFalse(v.afd_sensor(s))


class TestAfdValor(unittest.TestCase):
    def test_aceita(self):
        for s in ["0.01", "0.1", "0.10", "1", "24.5", "60", "100", "10.00",
                  "99999.99", "1500000.75", "007", "000.01"]:
            with self.subTest(s=s):
                self.assertTrue(v.afd_valor(s))

    def test_rejeita(self):
        for s in ["", "0", "0.0", "0.00", "00.00", "0.001", "1.234", ".5",
                  "5.", "1,5", "-1", "+1", "1e3", " 1", "1 ", "AA", "1.2.3"]:
            with self.subTest(s=s):
                self.assertFalse(v.afd_valor(s))


class TestAfdUnidade(unittest.TestCase):
    def test_aceita(self):
        for s in ["CELSIUS", "PERCENTUAL"]:
            self.assertTrue(v.afd_unidade(s))

    def test_rejeita(self):
        for s in ["", "celsius", "CELSIU", "CELSIUSS", "PERCENT", "KELVIN",
                  " CELSIUS", "C"]:
            with self.subTest(s=s):
                self.assertFalse(v.afd_unidade(s))


class TestLexico(unittest.TestCase):
    def tipos(self, texto):
        return [t.tipo for t in v.tokenizar(texto)]

    def test_tags(self):
        self.assertEqual(self.tipos("<leitura>"), [v.OPEN])
        self.assertEqual(self.tipos("</leitura>"), [v.CLOSE])
        self.assertEqual(self.tipos("<leitura >"), [v.OPEN])
        self.assertEqual(self.tipos("</leitura\n>"), [v.CLOSE])

    def test_tags_invalidas(self):
        for tag in ["< leitura>", "</ leitura>", "<valor/>", '<leitura id="1">',
                    "<sensor1>", "<>", "</>"]:
            with self.subTest(tag=tag):
                self.assertEqual(self.tipos(tag), [v.INVALIDO])

    def test_ignorados(self):
        self.assertEqual(self.tipos('<?xml version="1.0"?>\n<!-- x -->\n  '), [])

    def test_comentario_sem_fim(self):
        self.assertEqual(self.tipos("<!-- x <leitura>"), [v.INVALIDO])


class TestValidarXml(unittest.TestCase):
    def test_valido(self):
        self.assertEqual(v.validar_xml(f"<telemetria>{LEITURA_OK}</telemetria>"), [])

    def test_raiz_sem_leituras(self):
        self.assertEqual(v.validar_xml("<telemetria></telemetria>"), [])

    def test_vazio(self):
        for texto in ["", "   \n\t", "<?xml version='1.0'?>", "<!-- só -->"]:
            with self.subTest(texto=texto):
                self.assertEqual(v.validar_xml(texto), ["Erro: Arquivo xml vazio"])

    def test_conteudo_antes_da_raiz(self):
        self.assertEqual(
            v.validar_xml(f"lixo<telemetria>{LEITURA_OK}</telemetria>"),
            ["Erro sintático: Conteúdo fora do elemento <telemetria> em lixo."])

    def test_conteudo_depois_da_raiz(self):
        self.assertEqual(
            v.validar_xml(f"<telemetria>{LEITURA_OK}</telemetria>fim"),
            ["Erro sintático: Conteúdo fora do elemento <telemetria> em fim."])

    def test_raiz_aninhada(self):
        self.assertEqual(
            v.validar_xml(f"<telemetria><telemetria>{LEITURA_OK}"
                          f"</telemetria></telemetria>"),
            ["Erro sintático: Elemento <telemetria> repetido em <telemetria>.",
             "Erro sintático: Elemento <telemetria> repetido em </telemetria>."])

    def test_sem_raiz(self):
        self.assertEqual(
            v.validar_xml(LEITURA_OK),
            ["Erro sintático: Elemento <telemetria> não foi aberto.",
             "Erro sintático: Elemento <telemetria> não foi fechado."])

    def test_detalhes_tipo(self):
        xml = ("<telemetria>\n<leitura><sensor>UMID_02</sensor><valor>AA"
               "</valor><unidade>PERCENTUAL</unidade></leitura>\n</telemetria>")
        erros = v.validar_xml(xml, detalhes=True)
        self.assertEqual(len(erros), 2)
        self.assertTrue(erros[0].startswith(
            "Erro de validação na linha 1: Tipo de dados inválido"))
        self.assertEqual(
            erros[1],
            "  -> linha 2 do arquivo: <valor>AA</valor>: o caractere 'A' "
            "(posição 1) não tem transição a partir do estado INI; "
            "esperado número >= 0.01 com até 2 casas decimais.")

    def test_detalhes_estrutura(self):
        xml = ("<telemetria>\n<leitura><sensor>TEMP_01</sensor><valor>1"
               "</valor></leitura>\n</telemetria>")
        self.assertEqual(
            v.validar_xml(xml, detalhes=True)[1],
            "  -> linha 2 do arquivo: o AFD de estrutura parou no estado q7 "
            "ao ler </leitura>; esperado <unidade>.")

    def test_sem_detalhes_mantem_formato_do_enunciado(self):
        xml = f"<telemetria>{LEITURA_OK.replace('24.5', 'AA')}</telemetria>"
        self.assertEqual(len(v.validar_xml(xml)), 1)


class TestJflap(unittest.TestCase):
    """Os .jff de docs/automatos/ têm que ser os mesmos AFDs do código."""

    SIMBOLOS_ESTRUTURA = {
        "L": (v.OPEN, "leitura"), "l": (v.CLOSE, "leitura"),
        "S": (v.OPEN, "sensor"), "s": (v.CLOSE, "sensor"),
        "V": (v.OPEN, "valor"), "v": (v.CLOSE, "valor"),
        "U": (v.OPEN, "unidade"), "u": (v.CLOSE, "unidade"), "t": v.TEXT,
    }

    def ler_jff(self, nome, simbolos):
        raiz = ET.parse(RAIZ / "docs" / "automatos" / f"{nome}.jff").getroot()
        nomes = {e.get("id"): e.get("name") for e in raiz.iter("state")}
        inicial = [e.get("name") for e in raiz.iter("state")
                   if e.find("initial") is not None]
        finais = {e.get("name") for e in raiz.iter("state")
                  if e.find("final") is not None}
        delta = {(nomes[t.findtext("from")],
                  simbolos.get(t.findtext("read"), t.findtext("read"))):
                 nomes[t.findtext("to")] for t in raiz.iter("transition")}
        return inicial, finais, delta

    def comparar(self, nome, afd, simbolos):
        inicial, finais, delta = self.ler_jff(nome, simbolos)
        self.assertEqual(inicial, [str(afd["inicial"])])
        self.assertEqual(finais, {str(e) for e in afd["aceitacao"]})
        self.assertEqual(delta, {(str(o), s): str(d)
                                 for (o, s), d in afd["delta"].items()})

    def test_estrutura(self):
        afd = {"delta": v.TRANSICOES_ESTRUTURA, "inicial": "q0",
               "aceitacao": v.ACEITACAO_ESTRUTURA}
        self.comparar("afd_estrutura", afd, self.SIMBOLOS_ESTRUTURA)

    def test_sensor(self):
        self.comparar("afd_sensor", v.AFD_SENSOR, {"l": "L", "d": "D"})

    def test_valor(self):
        self.comparar("afd_valor", v.AFD_VALOR, {"z": "Z", "n": "NZ", "p": "P"})

    def test_unidade(self):
        self.comparar("afd_unidade", v.AFD_UNIDADE, {})


if __name__ == "__main__":
    unittest.main()
