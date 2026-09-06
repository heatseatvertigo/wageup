"""Estruturas e utilidades comuns aos leitores de extrato bancario.

Cada formato (OFX, CSV, PDF) tem o seu modulo e devolve a mesma coisa: uma
lista de ParsedTransaction. Quem chama nao precisa saber de qual arquivo veio.
"""
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Mesmo limite do campo description em Transaction.
MAX_DESCRIPTION = 180


class StatementError(Exception):
    """Arquivo que nao da para ler.

    A mensagem vai direto para a tela, entao escreva em portugues e diga o que
    o usuario pode fazer a respeito.
    """


@dataclass
class ParsedTransaction:
    """Um lancamento lido do extrato, antes de virar Transaction.

    `amount` e sempre positivo: o sinal do extrato ja foi traduzido em `type`.
    Guardar valor negativo aqui obrigaria todo consumidor a lembrar do sinal.
    """

    external_id: str
    occurred_at: datetime
    amount: Decimal
    type: str  # "income" ou "expense"
    description: str

    def as_dict(self):
        return {
            "external_id": self.external_id,
            "occurred_at": self.occurred_at.isoformat(),
            "amount": str(self.amount),
            "type": self.type,
            "description": self.description,
        }


def clean_description(*partes):
    """Junta os pedacos de descricao, tira excesso de espaco e corta no limite."""
    vistos = []
    for parte in partes:
        texto = re.sub(r"\s+", " ", (parte or "")).strip()
        if not texto:
            continue
        # Banco costuma repetir o mesmo texto em dois campos. Sem esta checagem
        # a descricao sai como "PIX RECEBIDO - PIX RECEBIDO".
        if any(texto.casefold() in visto.casefold() for visto in vistos):
            continue
        vistos = [visto for visto in vistos if visto.casefold() not in texto.casefold()]
        vistos.append(texto)
    return " - ".join(vistos)[:MAX_DESCRIPTION]


def parse_decimal(bruto):
    """Le valor monetario nos formatos que aparecem em extrato brasileiro.

    Aceita "340.00", "340,00", "1.234,56", "R$ 1.234,56", "-120,00" e
    "(120,00)" — parenteses significam negativo em alguns exportadores.
    """
    texto = unicodedata.normalize("NFKD", str(bruto or "")).strip()
    if not texto:
        raise StatementError("Valor vazio no extrato.")

    negativo = texto.startswith("(") and texto.endswith(")")
    texto = re.sub(r"[^\d,.\-]", "", texto)
    if not texto:
        raise StatementError(f"Valor irreconhecivel no extrato: {bruto!r}")

    if texto.startswith("-"):
        negativo = True
    texto = texto.replace("-", "")

    # Descobrir qual separador e o decimal sem saber o idioma do arquivo.
    separadores = {caractere for caractere in texto if caractere in ",."}
    corte = -1
    if len(separadores) == 2:
        # Os dois aparecem: o ultimo e o decimal. Vale para "1.234,56" e "1,234.56".
        corte = max(texto.rfind(","), texto.rfind("."))
    elif len(separadores) == 1:
        separador = separadores.pop()
        # Repetido significa milhar em toda ocorrencia: "1.234.567".
        # Uma unica ocorrencia com 3 digitos depois tambem e milhar: "1.234".
        if texto.count(separador) == 1 and len(texto.split(separador)[1]) in (1, 2):
            corte = texto.rfind(separador)

    if corte == -1:
        inteiro, decimal = texto, ""
    else:
        inteiro, decimal = texto[:corte], texto[corte + 1 :]
    inteiro = re.sub(r"[,.]", "", inteiro) or "0"

    try:
        valor = Decimal(f"{inteiro}.{decimal or '0'}")
    except InvalidOperation as exc:
        raise StatementError(f"Valor irreconhecivel no extrato: {bruto!r}") from exc

    return -valor if negativo else valor


def fingerprint(*partes):
    """Identificador estavel para lancamento sem ID proprio do banco.

    O mesmo arquivo lido duas vezes gera os mesmos identificadores, entao a
    reimportacao nao duplica. Formatos sem ID (CSV, PDF) dependem disto.
    """
    material = "|".join(str(parte) for parte in partes)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]


def desambiguar(transacoes):
    """Garante external_id unico dentro do mesmo arquivo.

    Dois cafes de R$ 12,00 no mesmo dia sao lancamentos diferentes com a mesma
    impressao digital. O sufixo mantem os dois, e continua deterministico: o
    mesmo arquivo gera sempre os mesmos sufixos.
    """
    contagem = {}
    for transacao in transacoes:
        base = transacao.external_id
        contagem[base] = contagem.get(base, 0) + 1
        if contagem[base] > 1:
            transacao.external_id = f"{base}-{contagem[base]}"
    return transacoes
