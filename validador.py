#!/usr/bin/env python3
"""
Projeto de Teoria da Computação
Grupo 04 - Validador de Estrutura XML Plana (telemetria de sensores)

Abordagem:
  1. Análise léxica: o arquivo inteiro vira uma sequência de tokens (tag de
     abertura, tag de fechamento, texto). Quebras de linha não importam.
     O nome de cada tag é reconhecido por um AFD.
  2. Elemento raiz: a sequência de tokens deve ter a forma
     <telemetria> X* </telemetria>, em que X é qualquer outro token.
  3. Análise estrutural: o conteúdo da raiz é dividido em blocos <leitura>
     e um AFD (autômato finito determinístico) reconhece cada bloco válido.
  4. Validação de tipos: cada conteúdo é testado por um AFD próprio
     (sensor, valor, unidade).

Uso:
    python validador.py [--detalhes] arquivo.xml

Com --detalhes, cada erro vem acompanhado da linha do arquivo e do ponto
em que o AFD rejeitou a entrada.
"""

import sys

# ---------------------------------------------------------------------------
# 0. EXECUÇÃO DE UM AFD
# ---------------------------------------------------------------------------
# Cada AFD é a quíntupla (Q, Σ, δ, q0, F) representada por:
#   delta     -> dicionário {(estado, símbolo): próximo estado}
#   inicial   -> q0
#   aceitacao -> F
#   classe    -> função que converte o caractere lido no símbolo de Σ
#                (agrupa caracteres equivalentes, ex.: '1'..'9' -> "NZ")
# Transição ausente em delta = estado de erro (rejeição imediata).

def rodar_afd(afd, cadeia):
    """Executa o AFD sobre a cadeia.
    Retorna (aceito, estado, posicao): o último estado alcançado e a
    posição do símbolo que não tinha transição (None se a cadeia foi lida
    até o fim)."""
    estado = afd["inicial"]
    for posicao, c in enumerate(cadeia):
        proximo = afd["delta"].get((estado, afd["classe"](c)))
        if proximo is None:
            return False, estado, posicao
        estado = proximo
    return estado in afd["aceitacao"], estado, None


def executar_afd(afd, cadeia):
    return rodar_afd(afd, cadeia)[0]


# ---------------------------------------------------------------------------
# 1. ANALISADOR LÉXICO
# ---------------------------------------------------------------------------
# Tipos de token
OPEN, CLOSE, TEXT, INVALIDO = "OPEN", "CLOSE", "TEXT", "INVALIDO"

LETRAS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITOS = "0123456789"

# --- nome de tag: uma ou mais letras ---------------------------------------
# Σ = {L} (L = letra).  INI -L-> NOME -L-> NOME;  F = {NOME}.
AFD_NOME_TAG = {
    "delta": {("INI", "L"): "NOME", ("NOME", "L"): "NOME"},
    "inicial": "INI",
    "aceitacao": {"NOME"},
    "classe": lambda c: "L" if c in LETRAS else None,
}


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

    Como no XML, não pode haver espaço logo depois de '<' ou '</'
    (< leitura> e </ leitura> são inválidos), mas pode haver antes do '>'
    (<leitura > é aceito).
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
            conteudo = texto[i + 1:fim].rstrip()
            if conteudo.startswith("/"):
                nome, tipo = conteudo[1:], CLOSE
            else:
                nome, tipo = conteudo, OPEN
            if executar_afd(AFD_NOME_TAG, nome):
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

CAMPOS = ("sensor", "valor", "unidade")

# Em qual estado cada texto lido pertence a qual campo
CAMPO_DO_ESTADO = {"q2": "sensor", "q5": "valor", "q8": "unidade"}


def validar_estrutura(tokens):
    """Executa o AFD de estrutura.
    Retorna (aceito, campos, estado, rejeitado): campos = {campo: token
    de texto}; estado é onde o AFD parou e rejeitado é o token que não
    tinha transição (None se o bloco foi lido até o fim)."""
    estado = "q0"
    campos = {}
    for token in tokens:
        tipo, valor = token.par()
        simbolo = TEXT if tipo == TEXT else (tipo, valor)
        proximo = TRANSICOES_ESTRUTURA.get((estado, simbolo))
        if proximo is None:
            return False, campos, estado, token
        if tipo == TEXT:
            campos[CAMPO_DO_ESTADO[estado]] = token
        estado = proximo
    return estado in ACEITACAO_ESTRUTURA, campos, estado, None


def esperados_estrutura(estado):
    """Símbolos que o AFD de estrutura aceitaria a partir do estado."""
    nomes = []
    for (origem, simbolo) in TRANSICOES_ESTRUTURA:
        if origem == estado:
            if simbolo == TEXT:
                nomes.append("texto")
            else:
                tipo, nome = simbolo
                nomes.append(f"<{nome}>" if tipo == OPEN else f"</{nome}>")
    return " ou ".join(nomes)


# ---------------------------------------------------------------------------
# 3. AFDs DOS TIPOS DE DADOS
# ---------------------------------------------------------------------------

# --- sensor: texto de tamanho exatamente 7, com pelo menos uma letra -------
# Σ = {L, D}, onde L = letra e D = dígito ou '_'.
# É o AFD produto de dois AFDs: um conta os caracteres lidos (0..7) e o
# outro lembra se já apareceu alguma letra. O estado "k" significa k
# caracteres lidos e nenhuma letra ainda; "kL" significa k caracteres
# lidos e pelo menos uma letra. Só "7L" é de aceitação, então uma cadeia
# só de dígitos, como "1234567", não é texto e é rejeitada.
# Nos estados 7 e 7L não há transição: um 8º caractere leva à rejeição.

def classe_sensor(c):
    if c in LETRAS:
        return "L"
    if c in DIGITOS or c == "_":
        return "D"
    return None


def construir_afd_sensor(tamanho):
    delta = {}
    for k in range(tamanho):
        delta[(str(k), "L")] = f"{k + 1}L"
        delta[(str(k), "D")] = str(k + 1)
        if k > 0:                               # o estado 0L não existe
            delta[(f"{k}L", "L")] = f"{k + 1}L"
            delta[(f"{k}L", "D")] = f"{k + 1}L"
    return {"delta": delta, "inicial": "0", "aceitacao": {f"{tamanho}L"},
            "classe": classe_sensor}


AFD_SENSOR = construir_afd_sensor(7)


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

AFD_DO_CAMPO = {"sensor": AFD_SENSOR, "valor": AFD_VALOR,
                "unidade": AFD_UNIDADE}

# Usado no modo --detalhes para dizer o que o campo deveria conter
TIPO_ESPERADO = {
    "sensor": "7 caracteres (letras, dígitos ou _) com pelo menos uma letra",
    "valor": "número >= 0.01 com até 2 casas decimais",
    "unidade": "CELSIUS ou PERCENTUAL",
}


def afd_sensor(cadeia):
    return executar_afd(AFD_SENSOR, cadeia)


def afd_valor(cadeia):
    return executar_afd(AFD_VALOR, cadeia)


def afd_unidade(cadeia):
    return executar_afd(AFD_UNIDADE, cadeia)


def campos_invalidos(valores):
    """Campos cujo conteúdo é rejeitado pelo AFD do seu tipo."""
    return [c for c in CAMPOS if not executar_afd(AFD_DO_CAMPO[c], valores[c])]


def motivo_tipo(campo, cadeia):
    """Explica onde o AFD do campo rejeitou a cadeia (modo --detalhes)."""
    _, estado, posicao = rodar_afd(AFD_DO_CAMPO[campo], cadeia)
    if posicao is not None:
        onde = (f"o caractere '{cadeia[posicao]}' (posição {posicao + 1}) "
                f"não tem transição a partir do estado {estado}")
    else:
        onde = f"a cadeia terminou no estado {estado}, que não é de aceitação"
    return (f"<{campo}>{cadeia}</{campo}>: {onde}; "
            f"esperado {TIPO_ESPERADO[campo]}.")


# ---------------------------------------------------------------------------
# 4. VALIDADOR DO ARQUIVO
# ---------------------------------------------------------------------------

RAIZ_ABRE, RAIZ_FECHA = (OPEN, "telemetria"), (CLOSE, "telemetria")


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


def validar_xml(conteudo, detalhes=False):
    """Retorna a lista de mensagens de erro (vazia = arquivo válido).

    Com detalhes=True, cada erro é seguido de linhas "  -> ..." com a linha
    do arquivo e o ponto em que o AFD rejeitou a entrada."""
    tokens = tokenizar(conteudo)
    if not tokens:
        return ["Erro: Arquivo xml vazio"]

    erros = []

    def erro(mensagem, *motivos):
        erros.append(mensagem)
        if detalhes:
            erros.extend(f"  -> {m}" for m in motivos)

    def linha(token):
        return conteudo.count("\n", 0, token.inicio) + 1

    def trecho(bloco):
        return trecho_original(conteudo, bloco)

    # --- Elemento raiz: o arquivo deve ser <telemetria> X* </telemetria> ---
    abre = [i for i, t in enumerate(tokens) if t.par() == RAIZ_ABRE]
    inicio = abre[0] + 1 if abre else 0
    fecha = [i for i in range(inicio, len(tokens))
             if tokens[i].par() == RAIZ_FECHA]
    fim = fecha[-1] if fecha else len(tokens)

    if not abre:
        erro("Erro sintático: Elemento <telemetria> não foi aberto.",
             f"linha {linha(tokens[0])} do arquivo: o arquivo começa com "
             f"{trecho(tokens[:1])}, e não com <telemetria>.")
    elif abre[0] > 0:
        antes = tokens[:abre[0]]
        erro(f"Erro sintático: Conteúdo fora do elemento <telemetria> em "
             f"{trecho(antes)}.",
             f"linha {linha(antes[0])} do arquivo: há conteúdo antes de "
             f"<telemetria>.")

    conteudo_raiz = []
    for token in tokens[inicio:fim]:
        if token.par() in (RAIZ_ABRE, RAIZ_FECHA):
            erro(f"Erro sintático: Elemento <telemetria> repetido em "
                 f"{trecho([token])}.",
                 f"linha {linha(token)} do arquivo: só pode haver um "
                 f"elemento raiz.")
        else:
            conteudo_raiz.append(token)

    if not fecha:
        erro("Erro sintático: Elemento <telemetria> não foi fechado.",
             f"linha {linha(tokens[-1])} do arquivo: o arquivo termina com "
             f"{trecho(tokens[-1:])}, e não com </telemetria>.")
    elif fim < len(tokens) - 1:
        depois = tokens[fim + 1:]
        erro(f"Erro sintático: Conteúdo fora do elemento <telemetria> em "
             f"{trecho(depois)}.",
             f"linha {linha(depois[0])} do arquivo: há conteúdo depois de "
             f"</telemetria>.")

    # --- Leituras: cada bloco é uma leitura, numerada a partir de 1 -------
    # (como no exemplo do enunciado)
    for numero, bloco in enumerate(separar_blocos(conteudo_raiz), start=1):
        prefixo = f"Erro de validação na linha {numero}: "
        aceito, campos, estado, rejeitado = validar_estrutura(bloco)
        if not aceito:
            if rejeitado is not None:
                motivo = (f"linha {linha(rejeitado)} do arquivo: o AFD de "
                          f"estrutura parou no estado {estado} ao ler "
                          f"{trecho([rejeitado])}; esperado "
                          f"{esperados_estrutura(estado)}.")
            else:
                motivo = (f"linha {linha(bloco[-1])} do arquivo: a leitura "
                          f"terminou no estado {estado}, que não é de "
                          f"aceitação; esperado {esperados_estrutura(estado)}.")
            erro(f"{prefixo}Estrutura inválida em {trecho(bloco)}.", motivo)
            continue

        valores = {c: campos[c].valor if c in campos else "" for c in CAMPOS}
        invalidos = campos_invalidos(valores)
        if invalidos:
            erro(f"{prefixo}Tipo de dados inválido em {trecho(bloco)}.",
                 *(f"linha {linha(campos.get(c, bloco[0]))} do arquivo: "
                   f"{motivo_tipo(c, valores[c])}" for c in invalidos))
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


OPCOES_DETALHES = ("-d", "--detalhes")


def main():
    # Garante a acentuação correta mesmo quando a saída é redirecionada
    # ou exibida em terminais que não usam a codificação padrão do Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    argumentos = sys.argv[1:]
    detalhes = any(a in OPCOES_DETALHES for a in argumentos)
    arquivos = [a for a in argumentos if a not in OPCOES_DETALHES]
    if len(arquivos) != 1:
        print("Uso: python validador.py [--detalhes] arquivo.xml")
        sys.exit(2)
    try:
        conteudo = ler_arquivo(arquivos[0])
    except OSError as e:
        print(f"Erro: não foi possível abrir o arquivo ({e.strerror}).")
        sys.exit(2)

    erros = validar_xml(conteudo, detalhes)
    if erros:
        for e in erros:
            print(e)
        sys.exit(1)
    print("Sucesso: Arquivo XML válido.")


if __name__ == "__main__":
    main()
