#!/usr/bin/env python3
"""
Projeto de Teoria da Computação
Grupo 04 - Validador de Estrutura XML Plana (telemetria de sensores)

Abordagem:
  1. Análise léxica: o arquivo inteiro vira uma sequência de tokens (tag de
     abertura, tag de fechamento, texto). Quebras de linha não importam.
  2. Análise estrutural: a sequência é dividida em blocos <leitura> e um
     AFD (autômato finito determinístico) reconhece cada bloco válido.
  3. Validação de tipos: cada conteúdo é testado por um AFD próprio
     (sensor, valor, unidade).

Uso:
    python validador.py arquivo.xml
"""

import sys

# ---------------------------------------------------------------------------
# 1. ANALISADOR LÉXICO
# ---------------------------------------------------------------------------
# Tipos de token
OPEN, CLOSE, TEXT, INVALIDO = "OPEN", "CLOSE", "TEXT", "INVALIDO"

LETRAS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITOS = "0123456789"


class Token:
    """Um token com o trecho do arquivo de onde veio (início e fim),
    para poder mostrar o texto original nas mensagens de erro."""

    def __init__(self, tipo, valor, inicio, fim):
        self.tipo, self.valor = tipo, valor
        self.inicio, self.fim = inicio, fim

    def par(self):
        return (self.tipo, self.valor)

    def __repr__(self):
        return f"{self.tipo}({self.valor!r})"


def tokenizar(texto):
    """Converte o texto (arquivo inteiro ou uma linha) em lista de Tokens.

    As quebras de linha não importam: o arquivo é lido como uma única
    sequência de símbolos. Espaços entre tags são ignorados, assim como
    a declaração <?xml ...?> e comentários <!-- ... -->.
    """
    tokens = []
    i, n = 0, len(texto)
    while i < n:
        if texto.startswith("<!--", i):         # comentário
            fim = texto.find("-->", i + 4)
            if fim == -1:
                tokens.append(Token(INVALIDO, texto[i:], i, n))
                break
            i = fim + 3
        elif texto.startswith("<?", i):         # declaração <?xml ... ?>
            fim = texto.find("?>", i + 2)
            if fim == -1:
                tokens.append(Token(INVALIDO, texto[i:], i, n))
                break
            i = fim + 2
        elif texto[i] == "<":
            fim = texto.find(">", i)
            proximo_abre = texto.find("<", i + 1)
            if fim == -1 or (proximo_abre != -1 and proximo_abre < fim):
                # '<' sem '>' correspondente
                ate = n if proximo_abre == -1 else proximo_abre
                tokens.append(Token(INVALIDO, texto[i:ate], i, ate))
                i = ate
                continue
            conteudo = texto[i + 1:fim].strip()
            if conteudo.startswith("/"):
                nome = conteudo[1:].strip()
                tipo = CLOSE
            else:
                nome = conteudo
                tipo = OPEN
            if nome and all(c in LETRAS for c in nome):
                tokens.append(Token(tipo, nome, i, fim + 1))
            else:
                tokens.append(Token(INVALIDO, texto[i:fim + 1], i, fim + 1))
            i = fim + 1
        else:
            fim = texto.find("<", i)
            if fim == -1:
                fim = n
            trecho = texto[i:fim]
            if trecho.strip():                  # ignora espaços entre tags
                tokens.append(Token(TEXT, trecho, i, fim))
            i = fim
    return tokens


# ---------------------------------------------------------------------------
# 2. AFD DA ESTRUTURA DE UM BLOCO <leitura>
# ---------------------------------------------------------------------------
# Linguagem reconhecida:
#   <leitura> <sensor> T? </sensor> <valor> T? </valor>
#             <unidade> T? </unidade> </leitura>
# (T = texto; o texto é opcional para que um campo vazio seja tratado
#  como erro de TIPO, e não de estrutura.)
#
# Estados: q0 ... q11, com q11 como único estado de aceitação.
# Qualquer transição não definida leva ao estado de erro (rejeição).

TRANSICOES_ESTRUTURA = {
    ("q0", (OPEN, "leitura")): "q1",
    ("q1", (OPEN, "sensor")): "q2",
    ("q2", TEXT): "q3",
    ("q2", (CLOSE, "sensor")): "q4",
    ("q3", (CLOSE, "sensor")): "q4",
    ("q4", (OPEN, "valor")): "q5",
    ("q5", TEXT): "q6",
    ("q5", (CLOSE, "valor")): "q7",
    ("q6", (CLOSE, "valor")): "q7",
    ("q7", (OPEN, "unidade")): "q8",
    ("q8", TEXT): "q9",
    ("q8", (CLOSE, "unidade")): "q10",
    ("q9", (CLOSE, "unidade")): "q10",
    ("q10", (CLOSE, "leitura")): "q11",
}
ACEITACAO_ESTRUTURA = {"q11"}

# Em qual estado cada texto lido pertence a qual campo
CAMPO_DO_ESTADO = {"q2": "sensor", "q5": "valor", "q8": "unidade"}


def validar_estrutura(tokens):
    """Executa o AFD de estrutura.
    Retorna (aceito, campos) onde campos = {sensor, valor, unidade}."""
    estado = "q0"
    campos = {"sensor": "", "valor": "", "unidade": ""}
    for token in tokens:
        tipo, valor = token.par()
        simbolo = TEXT if tipo == TEXT else (tipo, valor)
        proximo = TRANSICOES_ESTRUTURA.get((estado, simbolo))
        if proximo is None:
            return False, None
        if tipo == TEXT:
            campos[CAMPO_DO_ESTADO[estado]] = valor
        estado = proximo
    return estado in ACEITACAO_ESTRUTURA, campos


# ---------------------------------------------------------------------------
# 3. AFDs DOS TIPOS DE DADOS
# ---------------------------------------------------------------------------
# Cada AFD é a quíntupla (Q, Σ, δ, q0, F) representada por:
#   delta     -> dicionário {(estado, símbolo): próximo estado}
#   inicial   -> q0
#   aceitacao -> F
#   classe    -> função que converte o caractere lido no símbolo de Σ
#                (agrupa caracteres equivalentes, ex.: '1'..'9' -> "NZ")
# Transição ausente em delta = estado de erro (rejeição imediata).

def executar_afd(afd, cadeia):
    estado = afd["inicial"]
    for c in cadeia:
        estado = afd["delta"].get((estado, afd["classe"](c)))
        if estado is None:
            return False
    return estado in afd["aceitacao"]


# --- sensor: texto de tamanho exatamente 7 (letras, dígitos ou '_') --------
# Σ = {C}, onde C é qualquer letra, dígito ou '_'.
# Estados 0..7 contam os caracteres lidos; 7 é o único de aceitação.
# No estado 7 não há transição, então um 8º caractere leva à rejeição.

def classe_sensor(c):
    return "C" if c in LETRAS or c in DIGITOS or c == "_" else None


AFD_SENSOR = {
    "delta": {(i, "C"): i + 1 for i in range(7)},
    "inicial": 0,
    "aceitacao": {7},
    "classe": classe_sensor,
}


# --- valor: número com até 2 casas decimais e mínimo 0.01 -----------------
# Σ = {Z, NZ, P}  (Z = '0', NZ = '1'..'9', P = '.')
# Os estados com sufixo _Z indicam que até agora só foram lidos zeros.
# Como há no máximo 2 casas decimais, qualquer dígito diferente de zero
# garante valor >= 0.01; por isso os estados _Z nunca são de aceitação
# (rejeita 0, 0.0, 0.00).
#
#   INI    -Z-> INT_Z    -NZ-> INT
#   INT_Z  -Z-> INT_Z    -NZ-> INT     -P-> PONTO_Z
#   INT    -Z,NZ-> INT                 -P-> PONTO
#   PONTO_Z -Z-> DEC1_Z  -NZ-> DEC1
#   PONTO   -Z,NZ-> DEC1
#   DEC1_Z  -Z-> DEC2_Z  -NZ-> DEC2
#   DEC1    -Z,NZ-> DEC2
#   DEC2_Z, DEC2: sem transições (uma 3ª casa decimal é rejeitada)

def classe_valor(c):
    if c == "0":
        return "Z"
    if c in DIGITOS:
        return "NZ"
    if c == ".":
        return "P"
    return None


AFD_VALOR = {
    "delta": {
        ("INI", "Z"): "INT_Z",        ("INI", "NZ"): "INT",
        ("INT_Z", "Z"): "INT_Z",      ("INT_Z", "NZ"): "INT",
        ("INT_Z", "P"): "PONTO_Z",
        ("INT", "Z"): "INT",          ("INT", "NZ"): "INT",
        ("INT", "P"): "PONTO",
        ("PONTO_Z", "Z"): "DEC1_Z",   ("PONTO_Z", "NZ"): "DEC1",
        ("PONTO", "Z"): "DEC1",       ("PONTO", "NZ"): "DEC1",
        ("DEC1_Z", "Z"): "DEC2_Z",    ("DEC1_Z", "NZ"): "DEC2",
        ("DEC1", "Z"): "DEC2",        ("DEC1", "NZ"): "DEC2",
    },
    "inicial": "INI",
    "aceitacao": {"INT", "DEC1", "DEC2"},
    "classe": classe_valor,
}


# --- unidade: linguagem finita {CELSIUS, PERCENTUAL} -----------------------
# Toda linguagem finita é regular. O AFD é montado como uma árvore de
# prefixos: cada letra lida avança um estado e o último estado de cada
# palavra é de aceitação. Aqui Σ são os próprios caracteres.

def construir_afd_palavras(palavras):
    delta, aceitacao, proximo_livre = {}, set(), 1
    for p in palavras:
        estado = 0
        for c in p:
            if (estado, c) not in delta:
                delta[(estado, c)] = proximo_livre
                proximo_livre += 1
            estado = delta[(estado, c)]
        aceitacao.add(estado)
    return {"delta": delta, "inicial": 0, "aceitacao": aceitacao,
            "classe": lambda c: c}


AFD_UNIDADE = construir_afd_palavras(["CELSIUS", "PERCENTUAL"])


def afd_sensor(cadeia):
    return executar_afd(AFD_SENSOR, cadeia)


def afd_valor(cadeia):
    return executar_afd(AFD_VALOR, cadeia)


def afd_unidade(cadeia):
    return executar_afd(AFD_UNIDADE, cadeia)


def validar_tipos(campos):
    return (afd_sensor(campos["sensor"])
            and afd_valor(campos["valor"])
            and afd_unidade(campos["unidade"]))


# ---------------------------------------------------------------------------
# 4. VALIDADOR DO ARQUIVO
# ---------------------------------------------------------------------------

def separar_blocos(tokens):
    """Divide a sequência de tokens em blocos candidatos a <leitura>.

    Um bloco termina em </leitura>; um novo <leitura> também fecha o bloco
    anterior (que ficou sem </leitura>). Assim um erro em uma leitura não
    contamina as seguintes, e a quebra de linha do arquivo não importa.
    """
    blocos, atual = [], []
    for token in tokens:
        if token.par() == (OPEN, "leitura") and atual:
            blocos.append(atual)
            atual = []
        atual.append(token)
        if token.par() == (CLOSE, "leitura"):
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    return blocos


def trecho_original(conteudo, bloco):
    """Texto do bloco como aparece no arquivo, juntado em uma linha só."""
    trecho = conteudo[bloco[0].inicio:bloco[-1].fim]
    return "".join(parte.strip() for parte in trecho.splitlines())


def validar_xml(conteudo):
    """Retorna a lista de mensagens de erro (vazia = arquivo válido)."""
    tokens = tokenizar(conteudo)
    if not tokens:
        return ["Erro: Arquivo xml vazio"]

    erros = []
    inicio, fim = 0, len(tokens)
    if tokens[0].par() == (OPEN, "telemetria"):
        inicio = 1
    else:
        erros.append("Erro sintático: Elemento <telemetria> não foi aberto.")

    if fim > inicio and tokens[-1].par() == (CLOSE, "telemetria"):
        fim -= 1
    else:
        erros.append("Erro sintático: Elemento <telemetria> não foi fechado.")

    # Cada bloco entre <telemetria> e </telemetria> é uma leitura,
    # numerada a partir de 1 (como no exemplo do enunciado).
    for numero, bloco in enumerate(separar_blocos(tokens[inicio:fim]),
                                   start=1):
        texto = trecho_original(conteudo, bloco)
        aceito, campos = validar_estrutura(bloco)
        if not aceito:
            erros.append(f"Erro de validação na linha {numero}: "
                         f"Estrutura inválida em {texto}.")
        elif not validar_tipos(campos):
            erros.append(f"Erro de validação na linha {numero}: "
                         f"Tipo de dados inválido em {texto}.")
    return erros


def ler_arquivo(caminho):
    """Lê o arquivo como UTF-8 (com ou sem BOM, já que o Bloco de Notas
    do Windows costuma gravar o BOM). Se não for UTF-8, tenta Latin-1."""
    with open(caminho, "rb") as f:
        dados = f.read()
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def main():
    # Garante a acentuação correta mesmo quando a saída é redirecionada
    # ou exibida em terminais que não usam a codificação padrão do Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) != 2:
        print("Uso: python validador.py arquivo.xml")
        sys.exit(2)
    try:
        conteudo = ler_arquivo(sys.argv[1])
    except OSError as e:
        print(f"Erro: não foi possível abrir o arquivo ({e.strerror}).")
        sys.exit(2)

    erros = validar_xml(conteudo)
    if erros:
        for e in erros:
            print(e)
        sys.exit(1)
    print("Sucesso: Arquivo XML válido.")


if __name__ == "__main__":
    main()
