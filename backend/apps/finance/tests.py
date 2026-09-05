"""Testes da importacao de extrato bancario.

O foco e o leitor de OFX e a deduplicacao. Sao as duas partes onde um erro
silencioso estraga o financeiro: leitura errada inverte entrada com saida, e
falha de deduplicacao duplica lancamento a cada reimportacao.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business

from .models import StatementImport, Transaction
from .statements import StatementError, parse_statement
from .statements.base import parse_decimal

# OFX 1.x: SGML, tags sem fechamento, acento em cp1252. E o que os bancos
# brasileiros exportam com mais frequencia.
OFX_SGML = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
ENCODING:USASCII
CHARSET:1252

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260902120000[-3:BRT]
<TRNAMT>340.00
<FITID>2026090200001
<MEMO>PIX RECEBIDO MARIA SOUZA
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260903
<TRNAMT>-120,50
<FITID>2026090300002
<NAME>PAGAMENTO
<MEMO>CONTA DE LUZ - REFERENCIA AGOSTO
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260904
<TRNAMT>-45.90
<FITID>2026090400003
<MEMO>MERCADO SAO JOAO
</STMTTRN>
</BANKTRANLIST>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""

# OFX 2.x: XML de verdade, com tags fechadas.
OFX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OFX>
  <BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
    <STMTTRN>
      <TRNTYPE>CREDIT</TRNTYPE>
      <DTPOSTED>20260910</DTPOSTED>
      <TRNAMT>1.500,00</TRNAMT>
      <FITID>xml-001</FITID>
      <MEMO>VENDA &amp; SERVICO</MEMO>
    </STMTTRN>
  </BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""

# Sem FITID: a deduplicacao passa a depender do conteudo.
OFX_SEM_FITID = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260905
<TRNAMT>-12,00
<MEMO>CAFE
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260905
<TRNAMT>-12,00
<MEMO>CAFE
</STMTTRN>
</BANKTRANLIST></OFX>
"""


class ParseDecimalTests(TestCase):
    def test_le_os_formatos_de_valor_que_aparecem_em_extrato(self):
        casos = {
            "340.00": Decimal("340.00"),
            "340,00": Decimal("340.00"),
            "1.234,56": Decimal("1234.56"),
            "1,234.56": Decimal("1234.56"),
            "R$ 1.234,56": Decimal("1234.56"),
            "-120,00": Decimal("-120.00"),
            "(120,00)": Decimal("-120.00"),
            "1.234.567,89": Decimal("1234567.89"),
        }
        for bruto, esperado in casos.items():
            with self.subTest(bruto=bruto):
                self.assertEqual(parse_decimal(bruto), esperado)

    def test_valor_sem_parte_decimal_e_lido_como_milhar(self):
        # "1.234" e mil duzentos e trinta e quatro, nao um real e vinte e tres.
        self.assertEqual(parse_decimal("1.234"), Decimal("1234"))

    def test_valor_vazio_avisa_em_vez_de_quebrar(self):
        with self.assertRaises(StatementError):
            parse_decimal("")


class LeituraOfxTests(TestCase):
    def test_le_ofx_sgml_com_acento_em_cp1252(self):
        formato, lancamentos = parse_statement("extrato.ofx", OFX_SGML.encode("cp1252"))

        self.assertEqual(formato, "ofx")
        self.assertEqual(len(lancamentos), 3)

        entrada = lancamentos[0]
        self.assertEqual(entrada.type, "income")
        self.assertEqual(entrada.amount, Decimal("340.00"))
        self.assertEqual(entrada.external_id, "2026090200001")
        self.assertEqual(entrada.description, "PIX RECEBIDO MARIA SOUZA")
        self.assertEqual(entrada.occurred_at.date().isoformat(), "2026-09-02")

        saida = lancamentos[1]
        self.assertEqual(saida.type, "expense")
        # O valor guardado e sempre positivo: o sinal virou o tipo.
        self.assertEqual(saida.amount, Decimal("120.50"))
        self.assertEqual(saida.description, "PAGAMENTO - CONTA DE LUZ - REFERENCIA AGOSTO")

    def test_le_ofx_xml_com_entidade_html(self):
        _, lancamentos = parse_statement("extrato.ofx", OFX_XML.encode("utf-8"))

        self.assertEqual(len(lancamentos), 1)
        self.assertEqual(lancamentos[0].amount, Decimal("1500.00"))
        self.assertEqual(lancamentos[0].description, "VENDA & SERVICO")

    def test_sem_fitid_gera_identificador_estavel_e_distinto(self):
        _, primeira = parse_statement("extrato.ofx", OFX_SEM_FITID.encode("utf-8"))
        _, segunda = parse_statement("extrato.ofx", OFX_SEM_FITID.encode("utf-8"))

        # Dois cafes iguais no mesmo dia sao lancamentos diferentes.
        self.assertNotEqual(primeira[0].external_id, primeira[1].external_id)
        # E ler o mesmo arquivo de novo tem de dar exatamente os mesmos ids,
        # senao a reimportacao duplicaria tudo.
        self.assertEqual(
            [item.external_id for item in primeira],
            [item.external_id for item in segunda],
        )

    def test_arquivo_sem_lancamento_avisa_o_usuario(self):
        with self.assertRaises(StatementError):
            parse_statement("extrato.ofx", b"<OFX></OFX>")

    def test_formato_nao_suportado_avisa_o_usuario(self):
        with self.assertRaises(StatementError):
            parse_statement("extrato.xlsx", b"qualquer coisa")


class ImportacaoEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@wageup.local", email="admin@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        self.business = Business.objects.create(owner=self.admin, name="Negocio")

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.admin).key}")

    def _arquivo(self, conteudo=None, nome="extrato.ofx"):
        return SimpleUploadedFile(nome, (conteudo or OFX_SGML.encode("cp1252")))

    def _preview(self, **kwargs):
        return self.client.post("/api/transactions/import/preview/", {"file": self._arquivo(**kwargs)})

    def _confirmar(self, preview, linhas=None):
        corpo = {
            "filename": preview["filename"],
            "file_format": preview["file_format"],
            "file_hash": preview["file_hash"],
            "transactions": linhas if linhas is not None else preview["transactions"],
        }
        return self.client.post("/api/transactions/import/confirm/", corpo, format="json")

    def test_preview_le_o_arquivo_e_nao_grava_nada(self):
        resposta = self._preview()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["total"], 3)
        self.assertEqual(resposta.data["duplicates"], 0)
        self.assertFalse(resposta.data["already_imported"])
        self.assertEqual(Transaction.objects.count(), 0)

    def test_confirmar_cria_os_lancamentos_com_origem_de_extrato(self):
        preview = self._preview().data
        resposta = self._confirmar(preview)

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.data["imported"], 3)
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertTrue(
            all(item.source == Transaction.Source.IMPORT for item in Transaction.objects.all())
        )
        self.assertEqual(StatementImport.objects.get().imported_count, 3)

    def test_reimportar_o_mesmo_extrato_nao_duplica(self):
        primeiro = self._preview().data
        self._confirmar(primeiro)

        segundo = self._preview().data
        self.assertEqual(segundo["duplicates"], 3)
        self.assertTrue(segundo["already_imported"])

        resposta = self._confirmar(segundo)
        self.assertEqual(resposta.data["imported"], 0)
        self.assertEqual(resposta.data["skipped"], 3)
        self.assertEqual(Transaction.objects.count(), 3)

    def test_usuario_pode_deixar_de_fora_o_que_nao_quer(self):
        preview = self._preview().data
        resposta = self._confirmar(preview, linhas=preview["transactions"][:1])

        self.assertEqual(resposta.data["imported"], 1)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_arquivo_de_outro_formato_responde_400(self):
        resposta = self._preview(conteudo=b"data;valor", nome="extrato.csv")

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Formato nao suportado", resposta.data["detail"])

    def test_member_nao_importa_extrato(self):
        User = get_user_model()
        member = User.objects.create_user(username="m@wageup.local", email="m@wageup.local", password="x")
        UserProfile.objects.create(user=member, role="member")
        Business.objects.create(owner=member, name="Outro")

        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=member).key}")
        resposta = cliente.post("/api/transactions/import/preview/", {"file": self._arquivo()})

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_extrato_de_um_negocio_nao_colide_com_o_de_outro(self):
        self._confirmar(self._preview().data)

        User = get_user_model()
        outro = User.objects.create_user(username="o@wageup.local", email="o@wageup.local", password="x")
        UserProfile.objects.create(user=outro, role="admin")
        Business.objects.create(owner=outro, name="Outro negocio")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=outro).key}")

        preview = cliente.post(
            "/api/transactions/import/preview/", {"file": self._arquivo()}
        ).data
        # O mesmo FITID em outro negocio nao e duplicata: a unicidade e por negocio.
        self.assertEqual(preview["duplicates"], 0)
