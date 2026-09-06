"""Leitor de extrato OFX.

Serve as duas versoes que os bancos brasileiros exportam:

- OFX 1.x, que e SGML — as tags abrem e nao fecham. Parser de XML engasga nele,
  por isso a leitura e por expressao regular sobre cada bloco <STMTTRN>.
- OFX 2.x, que e XML de verdade. O mesmo codigo serve: a regex para no "<"
  seguinte, entao a tag de fechamento nao atrapalha.

O que torna o OFX o melhor formato para importar: cada lancamento traz um
FITID, identificador atribuido pelo banco. E ele que faz reimportar o mesmo
extrato nao duplicar nada.
"""
import html
import re
from datetime import datetime, timedelta, timezone as tz

from django.utils import timezone

from .base import ParsedTransaction, StatementError, clean_description, desambiguar, fingerprint, parse_decimal

# Codificacoes que aparecem no cabecalho do OFX 1.x. Banco brasileiro costuma
# mandar CHARSET:1252 com acento; ler como UTF-8 estraga toda descricao.
CHARSETS = {
    "1252": "cp1252",
    "8859-1": "latin-1",
    "ISO-8859-1": "latin-1",
    "NONE": "utf-8",
    "UTF-8": "utf-8",
}

BLOCO_TRANSACAO = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.DOTALL | re.IGNORECASE)


def parse_ofx(conteudo):
    """Recebe os bytes do arquivo e devolve a lista de lancamentos."""
    texto = _decodificar(conteudo)

    blocos = BLOCO_TRANSACAO.findall(texto)
    if not blocos:
        raise StatementError(
            "Nenhum lancamento encontrado no arquivo. "
            "Confirme que e o extrato em OFX exportado pelo banco."
        )

    transacoes = []
    for posicao, bloco in enumerate(blocos):
        transacao = _ler_bloco(bloco, posicao)
        if transacao is not None:
            transacoes.append(transacao)

    if not transacoes:
        raise StatementError("O arquivo tem lancamentos, mas nenhum com valor valido.")

    return desambiguar(transacoes)


def _decodificar(conteudo):
    """Escolhe a codificacao pelo cabecalho e, na duvida, tenta as provaveis."""
    if isinstance(conteudo, str):
        return conteudo

    cabecalho = conteudo[:1024].decode("ascii", errors="ignore")
    candidatas = []
    for campo in ("CHARSET", "ENCODING"):
        achado = re.search(rf"{campo}\s*:\s*([\w-]+)", cabecalho, re.IGNORECASE)
        if achado:
            codec = CHARSETS.get(achado.group(1).upper())
            if codec:
                candidatas.append(codec)
    candidatas += ["utf-8", "cp1252"]

    for codec in candidatas:
        try:
            return conteudo.decode(codec)
        except (UnicodeDecodeError, LookupError):
            continue
    # Ultimo recurso: nao perder o extrato inteiro por causa de um byte solto.
    return conteudo.decode("latin-1", errors="replace")


def _tag(bloco, nome):
    """Valor de uma tag do bloco. Para no proximo '<' ou no fim da linha."""
    achado = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.IGNORECASE)
    return html.unescape(achado.group(1)).strip() if achado else ""


def _ler_bloco(bloco, posicao):
    bruto = _tag(bloco, "TRNAMT")
    if not bruto:
        return None

    valor = parse_decimal(bruto)
    if valor == 0:
        # Lancamento de valor zero e ajuste do banco, nao movimenta dinheiro.
        return None

    ocorrido_em = _ler_data(_tag(bloco, "DTPOSTED"))
    descricao = clean_description(_tag(bloco, "NAME"), _tag(bloco, "MEMO")) or _tag(bloco, "TRNTYPE") or "Lancamento"

    identificador = _tag(bloco, "FITID")
    if not identificador:
        # Sem FITID a deduplicacao passa a depender do conteudo. A posicao no
        # arquivo entra para nao fundir dois lancamentos identicos do mesmo dia.
        identificador = fingerprint("ofx", ocorrido_em.date(), valor, descricao, posicao)

    return ParsedTransaction(
        external_id=identificador[:120],
        occurred_at=ocorrido_em,
        amount=abs(valor),
        type="income" if valor > 0 else "expense",
        description=descricao,
    )


def _ler_data(bruto):
    """Le DTPOSTED, que vem como AAAAMMDD[HHMMSS][[-3:BRT]]."""
    achado = re.match(r"\s*(\d{8})(\d{6})?", bruto or "")
    if not achado:
        raise StatementError(f"Data irreconhecivel no extrato: {bruto!r}")

    dia = achado.group(1)
    hora = achado.group(2) or "120000"
    try:
        momento = datetime.strptime(dia + hora, "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise StatementError(f"Data invalida no extrato: {bruto!r}") from exc

    fuso = re.search(r"\[\s*([+-]?\d+(?:\.\d+)?)", bruto or "")
    if fuso:
        return momento.replace(tzinfo=tz(timedelta(hours=float(fuso.group(1)))))
    return timezone.make_aware(momento, timezone.get_default_timezone())
