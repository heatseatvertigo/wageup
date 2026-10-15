"""Testes da importacao de extrato bancario.

O foco e o leitor de OFX e a deduplicacao. Sao as duas partes onde um erro
silencioso estraga o financeiro: leitura errada inverte entrada com saida, e
falha de deduplicacao duplica lancamento a cada reimportacao.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business

from .models import Goal, StatementImport, Transaction
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


class JaLancadoNaPlataformaTests(TestCase):
    """O que foi lancado na plataforma aparece de novo no extrato do banco.

    A venda em dinheiro depositado, o PIX recebido fora da plataforma e o
    lancamento manual nao tem FITID, entao a deduplicacao por external_id nao
    os pega. Sem este aviso, importar o extrato contaria o mesmo dinheiro
    duas vezes.
    """

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@wageup.local", email="admin@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        self.business = Business.objects.create(owner=self.admin, name="Negocio")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.admin).key}")

    def _lancar(self, valor, dia, tipo=Transaction.TransactionType.INCOME, **campos):
        from datetime import datetime
        from django.utils import timezone

        dados = {"source": Transaction.Source.SALE, "description": "Venda: 2x Bolo"}
        dados.update(campos)
        return Transaction.objects.create(
            business=self.business, type=tipo, amount=Decimal(valor),
            occurred_at=timezone.make_aware(datetime(2026, 9, dia, 20, 0)), **dados,
        )

    def _preview(self, conteudo=OFX_SGML.encode("cp1252")):
        return self.client.post(
            "/api/transactions/import/preview/", {"file": SimpleUploadedFile("extrato.ofx", conteudo)}
        ).data

    def test_venda_ja_registrada_vem_marcada_como_parecida(self):
        self._lancar("340.00", 2)

        preview = self._preview()

        linha = preview["transactions"][0]
        self.assertEqual(linha["amount"], "340.00")
        self.assertEqual(linha["possible_match"]["description"], "Venda: 2x Bolo")
        self.assertEqual(linha["possible_match"]["source"], Transaction.Source.SALE)
        self.assertFalse(linha["duplicate"])
        self.assertEqual(preview["possible_matches"], 1)

    def test_venda_da_noite_casa_com_o_extrato_do_dia_seguinte(self):
        self._lancar("340.00", 1)

        self.assertIsNotNone(self._preview()["transactions"][0]["possible_match"])

    def test_dois_dias_de_distancia_nao_casa(self):
        self._lancar("340.00", 4)

        self.assertIsNone(self._preview()["transactions"][0]["possible_match"])

    def test_valor_ou_tipo_diferente_nao_casa(self):
        self._lancar("339.99", 2)
        self._lancar("340.00", 2, tipo=Transaction.TransactionType.EXPENSE)

        self.assertEqual(self._preview()["possible_matches"], 0)

    def test_lancamento_manual_tambem_e_reconhecido(self):
        self._lancar("120.50", 3, tipo=Transaction.TransactionType.EXPENSE,
                     source=Transaction.Source.MANUAL, description="Conta de luz")

        linha = self._preview()["transactions"][1]
        self.assertEqual(linha["possible_match"]["description"], "Conta de luz")

    def test_cada_lancamento_cobre_uma_linha_so(self):
        # O extrato tem dois cafes de 12,00 no mesmo dia; so um foi lancado.
        self._lancar("12.00", 5, tipo=Transaction.TransactionType.EXPENSE,
                     source=Transaction.Source.MANUAL, description="Cafe")

        linhas = self._preview(OFX_SEM_FITID.encode())["transactions"]

        self.assertEqual([linha["possible_match"] is not None for linha in linhas], [True, False])

    def test_o_que_veio_de_extrato_nao_conta_como_lancado_na_plataforma(self):
        self._lancar("340.00", 2, source=Transaction.Source.IMPORT, external_id="outro-banco-1")

        self.assertEqual(self._preview()["possible_matches"], 0)

    def test_lancamento_de_outro_negocio_nao_casa(self):
        from datetime import datetime
        from django.utils import timezone

        outro = get_user_model().objects.create_user(username="o@w.local", email="o@w.local", password="x")
        Transaction.objects.create(
            business=Business.objects.create(owner=outro, name="Outro"),
            type=Transaction.TransactionType.INCOME, amount=Decimal("340.00"),
            source=Transaction.Source.SALE, description="Alheia",
            occurred_at=timezone.make_aware(datetime(2026, 9, 2, 12, 0)),
        )

        self.assertEqual(self._preview()["possible_matches"], 0)


class InsightsTests(TestCase):
    """Os insights do dashboard leem a margem do modelo e sao so de admin."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@wageup.local", email="admin@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        self.business = Business.objects.create(owner=self.admin, name="Negocio")
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.admin).key}"
        )

    def _produto(self, nome, **campos):
        from apps.products.models import Product

        return Product.objects.create(business=self.business, name=nome, **campos)

    def test_melhor_margem_considera_taxas_e_nao_so_preco_menos_custo(self):
        # Por preco menos custo o "Caro" ganharia (60 contra 45). Descontadas
        # embalagem, taxa e imposto, quem rende mais e o "Enxuto".
        self._produto(
            "Caro", price=Decimal("200"), cost=Decimal("140"),
            other_costs=Decimal("30"), fee_percent=Decimal("5"), tax_percent=Decimal("6"),
        )
        self._produto(
            "Enxuto", price=Decimal("100"), cost=Decimal("55"),
            other_costs=Decimal("0"), fee_percent=Decimal("2"), tax_percent=Decimal("0"),
        )

        insights = self.client.get("/api/finance/insights/").data["insights"]

        melhor = next(i for i in insights if "margem" in i["title"].lower())
        self.assertIn("Enxuto", melhor["text"])

    def test_estoque_baixo_respeita_o_min_stock_cadastrado(self):
        # 12 unidades com minimo 20: baixo para este produto, embora acima do
        # limite fixo de 8 que a versao anterior usava para todo mundo.
        self._produto(
            "Torta", price=Decimal("50"), cost=Decimal("20"), stock=12, min_stock=20
        )

        insights = self.client.get("/api/finance/insights/").data["insights"]

        estoque = next(i for i in insights if i["title"] == "Estoque")
        self.assertIn("1 produto", estoque["text"])

    def test_member_nao_acessa(self):
        User = get_user_model()
        member = User.objects.create_user(
            username="mei@wageup.local", email="mei@wageup.local", password="x"
        )
        UserProfile.objects.create(user=member, role="member")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=member).key}")

        self.assertEqual(cliente.get("/api/finance/insights/").status_code, 403)

    def test_sem_login_nao_acessa(self):
        self.assertEqual(APIClient().get("/api/finance/insights/").status_code, 401)

    def test_produto_de_outro_negocio_nao_entra_nos_insights(self):
        from apps.products.models import Product

        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        Product.objects.create(
            business=Business.objects.create(owner=outro, name="Outro"),
            name="Alheio", price=Decimal("999"), cost=Decimal("1"),
        )
        self._produto("Meu", price=Decimal("100"), cost=Decimal("40"))

        insights = self.client.get("/api/finance/insights/").data["insights"]

        self.assertNotIn("Alheio", " ".join(i["text"] for i in insights))


@override_settings(ANTHROPIC_API_KEY="", DEEPSEEK_API_KEY="")
class MetaTests(TestCase):
    """Meta de faturamento do mes: conta igual no card, nos insights e no assistente."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@wageup.local", email="admin@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        self.business = Business.objects.create(owner=self.admin, name="Negocio")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.admin).key}")
        self.hoje = timezone.localdate()
        self.mes = f"{self.hoje.year:04d}-{self.hoje.month:02d}"

    def _entrada(self, valor, quando=None, tipo="income"):
        return Transaction.objects.create(
            business=self.business, description="x", type=tipo, amount=Decimal(valor),
            occurred_at=quando or timezone.now(),
        )

    def test_sem_meta_devolve_o_que_entrou_e_target_nulo(self):
        self._entrada("300")

        dados = self.client.get("/api/finance/goal/").data

        self.assertIsNone(dados["target"])
        self.assertEqual(dados["achieved"], Decimal("300.00"))
        self.assertEqual(dados["month"], self.mes)

    def test_define_meta_e_calcula_quanto_falta(self):
        self._entrada("3880")
        self._entrada("500", tipo="expense")  # saida nao conta para a meta

        dados = self.client.put("/api/finance/goal/", {"target_amount": "5000"}, format="json").data

        self.assertEqual(dados["target"], Decimal("5000.00"))
        self.assertEqual(dados["achieved"], Decimal("3880.00"))
        self.assertEqual(dados["remaining"], Decimal("1120.00"))
        self.assertEqual(dados["percent"], 77.6)
        self.assertFalse(dados["reached"])
        self.assertGreaterEqual(dados["days_left"], 1)

    def test_redefinir_atualiza_em_vez_de_duplicar(self):
        self.client.put("/api/finance/goal/", {"target_amount": "1000"}, format="json")
        self.client.put("/api/finance/goal/", {"target_amount": "2000"}, format="json")

        self.assertEqual(Goal.objects.filter(business=self.business).count(), 1)
        self.assertEqual(Goal.objects.get(business=self.business).target_amount, Decimal("2000.00"))

    def test_entrada_de_outro_mes_nao_conta(self):
        self._entrada("900", quando=timezone.now() - timedelta(days=40))
        self.client.put("/api/finance/goal/", {"target_amount": "1000"}, format="json")

        self.assertEqual(self.client.get("/api/finance/goal/").data["achieved"], Decimal("0.00"))

    def test_meta_batida(self):
        self._entrada("1500")

        dados = self.client.put("/api/finance/goal/", {"target_amount": "1000"}, format="json").data

        self.assertTrue(dados["reached"])
        self.assertEqual(dados["remaining"], Decimal("0.00"))

    def test_valores_invalidos_sao_recusados(self):
        for valor in ("0", "-10", "abc", "NaN", "Infinity", None):
            with self.subTest(valor=valor):
                resposta = self.client.put("/api/finance/goal/", {"target_amount": valor}, format="json")
                self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.client.get("/api/finance/goal/?month=2026-13").status_code, 400)

    def test_apagar_remove_a_meta(self):
        self.client.put("/api/finance/goal/", {"target_amount": "1000"}, format="json")

        dados = self.client.delete(f"/api/finance/goal/?month={self.mes}").data

        self.assertIsNone(dados["target"])
        self.assertFalse(Goal.objects.exists())

    def test_meta_de_outro_negocio_nao_aparece(self):
        User = get_user_model()
        outro = User.objects.create_user(username="z@w.local", email="z@w.local", password="x")
        Goal.objects.create(
            business=Business.objects.create(owner=outro, name="Outro"),
            month=self.hoje.replace(day=1), target_amount=Decimal("999"),
        )

        self.assertIsNone(self.client.get("/api/finance/goal/").data["target"])

    def test_member_nao_acessa(self):
        User = get_user_model()
        member = User.objects.create_user(username="mei@wageup.local", email="mei@wageup.local", password="x")
        UserProfile.objects.create(user=member, role="member")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=member).key}")

        self.assertEqual(cliente.get("/api/finance/goal/").status_code, 403)

    def test_insight_e_assistente_falam_quanto_falta(self):
        from .assistant import build_context, format_context

        self._entrada("3880")
        self.client.put("/api/finance/goal/", {"target_amount": "5000"}, format="json")

        insights = self.client.get("/api/finance/insights/").data["insights"]
        meta = next(i for i in insights if i["title"] == "Meta do mês")
        self.assertIn("Você está a R$ 1.120,00 da sua meta", meta["text"])

        texto = format_context(build_context(self.business))
        self.assertIn("Meta de faturamento: R$ 5.000,00. Já entrou R$ 3.880,00 (78%)", texto)
        self.assertIn("Entrou hoje: R$ 3.880,00", texto)
        self.assertIn("Melhor dia do mês:", texto)


@override_settings(ANTHROPIC_API_KEY="", DEEPSEEK_API_KEY="")
class InsightsDoMesTests(TestCase):
    """Os insights falam do mes, como os cards ao lado, e trazem botao de acao."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@wageup.local", email="admin@wageup.local", password="x"
        )
        UserProfile.objects.create(user=self.admin, role="admin")
        self.business = Business.objects.create(owner=self.admin, name="Negocio")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.admin).key}")

    def test_lancamento_antigo_nao_entra_na_saude_do_mes(self):
        Transaction.objects.create(
            business=self.business, description="antigo", type="income", amount=Decimal("12000"),
            occurred_at=timezone.now() - timedelta(days=70),
        )
        Transaction.objects.create(business=self.business, description="hoje", type="income", amount=Decimal("800"))

        insights = self.client.get("/api/finance/insights/").data["insights"]

        saude = next(i for i in insights if i["title"] == "Saúde do mês")
        self.assertIn("Sobrou R$ 800,00", saude["text"])
        self.assertNotIn("12.000", saude["text"])

    def test_melhor_margem_traz_acao_do_produto(self):
        from apps.products.models import Product

        produto = Product.objects.create(
            business=self.business, name="Bolo", price=Decimal("60"), cost=Decimal("20"), stock=30
        )

        insights = self.client.get("/api/finance/insights/").data["insights"]

        melhor = next(i for i in insights if i["title"] == "Melhor margem")
        self.assertEqual(melhor["action"], {"product_id": str(produto.id), "product_name": "Bolo", "type": "launch"})
        saude = next(i for i in insights if i["title"] == "Saúde do mês")
        self.assertIsNone(saude["action"])

    def test_ia_nao_vincula_produto_inventado(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.products.models import Product

        Product.objects.create(business=self.business, name="Bolo", price=Decimal("60"), cost=Decimal("20"), stock=30)
        resposta = SimpleNamespace(content=[SimpleNamespace(text=(
            '[{"title": "Divulgue o bolo", "text": "Rende bem.", "product_name": "bolo"},'
            ' {"title": "Outro", "text": "Texto.", "product_name": "Produto de outro negocio"}]'
        ))])

        with override_settings(ANTHROPIC_API_KEY="chave-teste"), patch("anthropic.Anthropic") as cliente:
            cliente.return_value.messages.create.return_value = resposta
            dados = self.client.get("/api/finance/insights/").data

        self.assertEqual(dados["provider"], "anthropic")
        self.assertEqual(dados["insights"][0]["action"]["product_name"], "Bolo")
        self.assertIsNone(dados["insights"][1]["action"])


@override_settings(ANTHROPIC_API_KEY="", DEEPSEEK_API_KEY="")
class ComparacaoDoMesTests(TestCase):
    """O mes corrente compara com o mesmo periodo do anterior, nao com o mes inteiro."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="a@w.local", email="a@w.local", password="x")
        UserProfile.objects.create(user=self.admin, role="admin")
        self.business = Business.objects.create(owner=self.admin, name="Negocio")

    def test_mes_anterior_conta_so_ate_o_mesmo_dia(self):
        from .insights import gather_metrics

        agora = timezone.localtime()
        inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        inicio_ant = (inicio - timedelta(days=1)).replace(day=1)
        # Dentro do mesmo periodo do mes anterior: conta.
        Transaction.objects.create(
            business=self.business, description="cedo", type="income", amount=Decimal("100"),
            occurred_at=inicio_ant + timedelta(hours=1),
        )
        # Depois do mesmo dia no mes anterior: fica de fora da comparacao.
        Transaction.objects.create(
            business=self.business, description="tarde", type="income", amount=Decimal("900"),
            occurred_at=inicio - timedelta(minutes=1),
        )

        metricas = gather_metrics(self.business)

        if agora.day < 28:
            self.assertEqual(metricas["prev_income"], 100.0)

    def test_servico_nao_conta_como_estoque_baixo(self):
        from apps.products.models import Product

        from .insights import gather_metrics

        Product.objects.create(
            business=self.business, name="Corte", unit=Product.Unit.SERVICE,
            price=Decimal("50"), cost=Decimal("5"), stock=0,
        )

        self.assertEqual(gather_metrics(self.business)["low_stock_count"], 0)
