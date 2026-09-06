"""Leitura de extrato bancario.

Ponto de entrada unico: `parse_statement`. Ele escolhe o leitor pela extensao
do arquivo e devolve sempre a mesma estrutura, seja qual for o formato.
"""
import hashlib
import os

from .base import ParsedTransaction, StatementError
from .ofx import parse_ofx

# Formatos que o projeto le hoje. CSV e PDF entram aqui quando os leitores
# deles existirem — nada mais precisa mudar fora deste dicionario.
LEITORES = {
    ".ofx": ("ofx", parse_ofx),
    ".ofc": ("ofx", parse_ofx),
}

EXTENSOES_ACEITAS = tuple(sorted(LEITORES))


def parse_statement(filename, conteudo):
    """Devolve (formato, lista de ParsedTransaction) para o arquivo recebido."""
    extensao = os.path.splitext(filename or "")[1].lower()
    leitor = LEITORES.get(extensao)
    if leitor is None:
        aceitas = ", ".join(EXTENSOES_ACEITAS)
        raise StatementError(
            f"Formato nao suportado ainda. Envie um extrato {aceitas} exportado pelo banco."
        )

    formato, funcao = leitor
    return formato, funcao(conteudo)


def hash_arquivo(conteudo):
    """Impressao digital do arquivo, para avisar quando ele ja foi importado.

    Guardamos o hash, nunca o arquivo: extrato bancario e dado sensivel e nao
    precisa ficar armazenado para a funcionalidade servir.
    """
    return hashlib.sha256(conteudo).hexdigest()


__all__ = [
    "EXTENSOES_ACEITAS",
    "ParsedTransaction",
    "StatementError",
    "hash_arquivo",
    "parse_statement",
]
