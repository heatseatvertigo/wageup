"""Testes da venda.

A venda e o que liga catalogo, estoque e financeiro. Os pontos que este
arquivo trava: o lucro sai da margem real (nao de preco menos custo), o
estoque nunca fica negativo nem mente, o financeiro recebe a entrada uma vez
so, e cancelar desfaz tudo isso.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business
from apps.finance.models import Transaction
from apps.payments.models import Payment
from apps.products.models import Product

from .models import Sale

SEGREDO = "segredo_teste"


class _VendasBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user, self.business, self.client = self._conta("admin@wageup.local", "admin")
        # Margem real por unidade: 60 - (18 + 4) - 11% de 60 (6,60) = 31,40.
        # Preco menos custo daria 42,00, que e o erro que a venda nao pode repetir.
        self.bolo = self._produto("Bolo de cenoura", price="60", cost="18", other_costs="4", stock=10)

    def _conta(self, email, role):
        User = get_user_model()
        user = User.objects.create_user(username=email, email=email, password="x")
        UserProfile.objects.create(user=user, role=role)
        business = Business.objects.create(owner=user, name=f"Negocio de {email}")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
        return user, business, cliente

    def _produto(self, nome, business=None, price="60", cost="18", other_costs="0", stock=10, **campos):
        dados = {"fee_percent": Decimal("5"), "tax_percent": Decimal("6")}
        dados.update(campos)
        return Product.objects.create(
            business=business or self.business, name=nome, price=Decimal(price),
            cost=Decimal(cost), other_costs=Decimal(other_costs), stock=stock, **dados,
        )

    def _vender(self, produto=None, quantidade=2, cliente=None, **campos):
        corpo = {"product_id": str((produto or self.bolo).id), "quantity": quantidade}
        corpo.update(campos)
        return (cliente or self.client).post("/api/sales/", corpo, format="json")


class RegistrarVendaTests(_VendasBase):
    def test_venda_baixa_o_estoque_e_lanca_a_entrada(self):
        resposta = self._vender(quantidade=3)

        self.assertEqual(resposta.status_code, 201)
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 7)
        lancamento = Transaction.objects.get()
        self.assertEqual(lancamento.type, Transaction.TransactionType.INCOME)
        self.assertEqual(lancamento.source, Transaction.Source.SALE)
        self.assertEqual(lancamento.amount, Decimal("180.00"))
        self.assertEqual(lancamento.business, self.business)
        self.assertEqual(Sale.objects.get().transaction, lancamento)

    def test_lucro_e_a_margem_real_vezes_a_quantidade(self):
        resposta = self._vender(quantidade=3)

        self.assertEqual(Decimal(resposta.data["profit"]), self.bolo.margin_value * 3)
        self.assertEqual(Decimal(resposta.data["profit"]), Decimal("94.20"))
        self.assertEqual(Decimal(resposta.data["fees"]), Decimal("19.80"))
        self.assertEqual(Decimal(resposta.data["cost_total"]), Decimal("66.00"))

    def test_preco_combinado_muda_o_total_e_a_taxa_mas_nao_o_custo(self):
        resposta = self._vender(quantidade=1, unit_price="50.00")

        self.assertEqual(Decimal(resposta.data["total"]), Decimal("50.00"))
        # 11% de 50 = 5,50; custo segue 22,00 do cadastro.
        self.assertEqual(Decimal(resposta.data["fees"]), Decimal("5.50"))
        self.assertEqual(Decimal(resposta.data["profit"]), Decimal("22.50"))

    def test_custo_vem_do_banco_mesmo_que_o_cliente_mande_outro(self):
        resposta = self._vender(quantidade=1, unit_cost="0.01", profit="999")

        self.assertEqual(Decimal(resposta.data["unit_cost"]), Decimal("22.00"))
        self.assertEqual(Decimal(resposta.data["profit"]), Decimal("31.40"))

    def test_valores_da_venda_nao_mudam_quando_o_produto_muda(self):
        self._vender(quantidade=1)
        self.bolo.price = Decimal("90")
        self.bolo.cost = Decimal("50")
        self.bolo.save()

        venda = Sale.objects.get()
        self.assertEqual(venda.total, Decimal("60.00"))
        self.assertEqual(venda.profit, Decimal("31.40"))

    def test_estoque_insuficiente_bloqueia_sem_gravar_nada(self):
        resposta = self._vender(quantidade=11)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Só há 10 em estoque", resposta.data["detail"])
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 10)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_vender_o_estoque_inteiro_zera_sem_ficar_negativo(self):
        self.assertEqual(self._vender(quantidade=10).status_code, 201)
        self.assertEqual(self._vender(quantidade=1).status_code, 400)

        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 0)

    def test_servico_nao_controla_estoque(self):
        consulta = self._produto("Consultoria", price="200", cost="0", stock=0, unit=Product.Unit.SERVICE)

        resposta = self._vender(consulta, quantidade=2)

        self.assertEqual(resposta.status_code, 201)
        consulta.refresh_from_db()
        self.assertEqual(consulta.stock, 0)
        self.assertEqual(Sale.objects.get().stock_moved, 0)

    def test_produto_inativo_nao_e_vendido(self):
        self.bolo.is_active = False
        self.bolo.save()

        resposta = self._vender()

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("inativo", resposta.data["detail"])

    def test_quantidade_zero_e_recusada(self):
        resposta = self._vender(quantidade=0)

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data["quantity"], ["Informe uma quantidade maior que zero."])

    def test_member_tambem_registra_venda(self):
        _, negocio_member, member = self._conta("mei@wageup.local", "member")
        brigadeiro = self._produto("Brigadeiro", business=negocio_member, price="3", cost="1")

        resposta = self._vender(brigadeiro, quantidade=5, cliente=member)

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(Transaction.objects.get().business, negocio_member)

    def test_sem_login_nao_vende(self):
        resposta = self._vender(cliente=APIClient())

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(Sale.objects.count(), 0)


class CancelarVendaTests(_VendasBase):
    def test_cancelar_devolve_o_estoque_e_tira_a_entrada(self):
        venda_id = self._vender(quantidade=4).data["id"]

        resposta = self.client.post(f"/api/sales/{venda_id}/cancel/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["status"], Sale.Status.CANCELED)
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 10)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_cancelar_duas_vezes_nao_devolve_estoque_em_dobro(self):
        venda_id = self._vender(quantidade=4).data["id"]

        self.client.post(f"/api/sales/{venda_id}/cancel/")
        self.client.post(f"/api/sales/{venda_id}/cancel/")

        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 10)

    def test_venda_cancelada_sai_do_resumo(self):
        venda_id = self._vender(quantidade=4).data["id"]
        self.client.post(f"/api/sales/{venda_id}/cancel/")

        resumo = self.client.get("/api/sales/summary/").data

        self.assertEqual(resumo["products"], [])
        self.assertEqual(resumo["totals"]["count"], 0)

    def test_produto_apagado_nao_apaga_a_venda(self):
        self._vender(quantidade=1)
        self.bolo.delete()

        venda = Sale.objects.get()
        self.assertIsNone(venda.product)
        self.assertEqual(venda.product_name, "Bolo de cenoura")
        self.assertEqual(venda.profit, Decimal("31.40"))
        lista = self.client.get("/api/sales/").data
        self.assertIsNone(lista[0]["product_id"])
        self.assertEqual(lista[0]["product_name"], "Bolo de cenoura")

    def test_nao_ha_rota_para_editar_ou_apagar_venda(self):
        venda_id = self._vender(quantidade=1).data["id"]

        self.assertEqual(self.client.patch(f"/api/sales/{venda_id}/", {"quantity": 9}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/sales/{venda_id}/").status_code, 405)


class ResumoTests(_VendasBase):
    def test_lucro_por_produto_do_que_mais_lucrou_ao_que_menos(self):
        brigadeiro = self._produto("Brigadeiro", price="3", cost="1", stock=100)
        self._vender(brigadeiro, quantidade=50)   # lucro 50 * (3 - 1 - 0,33) = 83,50
        self._vender(quantidade=1)                # lucro 31,40
        self._vender(quantidade=2)                # lucro 62,80 -> bolo 94,20

        resumo = self.client.get("/api/sales/summary/").data

        nomes = [item["product_name"] for item in resumo["products"]]
        self.assertEqual(nomes, ["Bolo de cenoura", "Brigadeiro"])
        bolo = resumo["products"][0]
        self.assertEqual(bolo["quantity"], 3)
        self.assertEqual(bolo["count"], 2)
        self.assertEqual(Decimal(bolo["profit"]), Decimal("94.20"))
        self.assertEqual(Decimal(resumo["products"][1]["profit"]), Decimal("83.50"))
        self.assertEqual(Decimal(resumo["totals"]["total"]), Decimal("330.00"))
        self.assertEqual(Decimal(resumo["totals"]["profit"]), Decimal("177.70"))

    def test_mes_pedido_separa_as_vendas(self):
        self._vender(quantidade=1)
        mes_passado = timezone.localtime() - timedelta(days=40)
        self._vender(quantidade=2, occurred_at=mes_passado.isoformat())

        este_mes = self.client.get("/api/sales/summary/").data
        anterior = self.client.get(f"/api/sales/summary/?month={mes_passado:%Y-%m}").data
        lista_anterior = self.client.get(f"/api/sales/?month={mes_passado:%Y-%m}").data

        self.assertEqual(este_mes["totals"]["quantity"], 1)
        self.assertEqual(anterior["totals"]["quantity"], 2)
        self.assertEqual(len(lista_anterior), 1)

    def test_mes_invalido_responde_400(self):
        self.assertEqual(self.client.get("/api/sales/summary/?month=2026-13").status_code, 400)
        self.assertEqual(self.client.get("/api/sales/?month=ontem").status_code, 400)


class IsolamentoTests(_VendasBase):
    def test_nao_vende_produto_de_outro_negocio(self):
        _, outro_negocio, _ = self._conta("outro@wageup.local", "admin")
        alheio = self._produto("Alheio", business=outro_negocio)

        resposta = self._vender(alheio, quantidade=1)

        self.assertEqual(resposta.status_code, 404)
        alheio.refresh_from_db()
        self.assertEqual(alheio.stock, 10)
        self.assertEqual(Sale.objects.count(), 0)

    def test_venda_de_outro_negocio_nao_aparece_nem_cancela(self):
        _, outro_negocio, outro = self._conta("outro@wageup.local", "admin")
        alheio = self._produto("Alheio", business=outro_negocio)
        venda_alheia = self._vender(alheio, quantidade=2, cliente=outro).data["id"]

        self.assertEqual(self.client.get("/api/sales/").data, [])
        self.assertEqual(self.client.get("/api/sales/summary/").data["products"], [])
        self.assertEqual(self.client.post(f"/api/sales/{venda_alheia}/cancel/").status_code, 404)
        self.assertEqual(Sale.objects.get().status, Sale.Status.DONE)


def _resposta_abacate(corpo):
    resposta = type("Resposta", (), {})()
    resposta.status_code = 200
    resposta.json = lambda: corpo
    return resposta


@override_settings(ABACATE_PAY_API_KEY="abc_dev_teste", ABACATE_PAY_WEBHOOK_SECRET=SEGREDO)
class VendaPorPixTests(_VendasBase):
    """Cobranca PIX de um produto: so vira venda quando o dinheiro entra."""

    def setUp(self):
        super().setUp()
        patcher = patch("apps.payments.services.requests.request")
        self.abacate = patcher.start()
        self.addCleanup(patcher.stop)
        self.abacate.return_value = _resposta_abacate({"data": {"id": "pix_char_1"}})

    def _cobrar(self, quantidade=2, produto=None):
        return self.client.post("/api/payments/", {
            "amount": "120.00", "description": "Bolo de cenoura",
            "product_id": str((produto or self.bolo).id), "quantity": quantidade,
        }, format="json")

    def _webhook(self, tipo="transparent.completed", event_id="log_1"):
        return APIClient().post(
            f"/api/payments/webhooks/abacatepay/?webhookSecret={SEGREDO}",
            {"id": event_id, "event": tipo, "data": {"transparent": {"id": "pix_char_1"}}},
            format="json",
        )

    def test_gerar_a_cobranca_nao_baixa_estoque_nem_cria_venda(self):
        resposta = self._cobrar()

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(Payment.objects.get().metadata["product_id"], str(self.bolo.id))
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 10)
        self.assertEqual(Sale.objects.count(), 0)

    def test_cobranca_acima_do_estoque_nem_e_gerada(self):
        resposta = self._cobrar(quantidade=11)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Só há 10", resposta.data["detail"])
        self.assertEqual(Payment.objects.count(), 0)
        self.abacate.assert_not_called()

    def test_pagamento_vira_venda_ligada_a_entrada_do_pix(self):
        self._cobrar()
        self._webhook()

        venda = Sale.objects.get()
        self.assertEqual(venda.payment_method, Sale.PaymentMethod.PIX)
        self.assertEqual(venda.quantity, 2)
        self.assertEqual(venda.total, Decimal("120.00"))
        self.assertEqual(venda.profit, Decimal("62.80"))
        self.assertEqual(venda.transaction.source, Transaction.Source.PIX)
        # Uma entrada so: a do PIX, que a venda reaproveita.
        self.assertEqual(Transaction.objects.count(), 1)
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 8)

    def test_webhook_e_consulta_juntos_criam_uma_venda(self):
        self._cobrar()
        self._webhook()
        self.abacate.return_value = _resposta_abacate({"data": {"status": "PAID"}})
        self.client.post(f"/api/payments/{Payment.objects.get().id}/check/")

        self.assertEqual(Sale.objects.count(), 1)
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 8)

    def test_estoque_que_acabou_antes_do_pagamento_zera_sem_bloquear(self):
        self._cobrar(quantidade=2)
        Product.objects.filter(pk=self.bolo.pk).update(stock=1)

        self._webhook()

        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 0)
        self.assertEqual(Sale.objects.get().stock_moved, 1)

    def test_estorno_cancela_a_venda_e_devolve_o_estoque(self):
        self._cobrar()
        self._webhook(event_id="log_1")
        self._webhook(tipo="transparent.refunded", event_id="log_2")

        venda = Sale.objects.get()
        self.assertEqual(venda.status, Sale.Status.CANCELED)
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.stock, 10)
        # A entrada fica e o estorno lanca a saida: o financeiro fecha em zero.
        self.assertEqual(Transaction.objects.filter(type=Transaction.TransactionType.INCOME).count(), 1)
        self.assertEqual(Transaction.objects.filter(type=Transaction.TransactionType.EXPENSE).count(), 1)

    def test_venda_de_pix_nao_e_cancelada_pela_tela(self):
        self._cobrar()
        self._webhook()

        resposta = self.client.post(f"/api/sales/{Sale.objects.get().id}/cancel/")

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Sale.objects.get().status, Sale.Status.DONE)

    def test_cobranca_avulsa_paga_nao_vira_venda(self):
        self.client.post("/api/payments/", {"amount": "50.00"}, format="json")
        self._webhook()

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_produto_de_outro_negocio_nao_entra_na_cobranca(self):
        _, outro_negocio, _ = self._conta("outro@wageup.local", "admin")
        alheio = self._produto("Alheio", business=outro_negocio)

        resposta = self._cobrar(produto=alheio)

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)


@override_settings(ANTHROPIC_API_KEY="", DEEPSEEK_API_KEY="")
class VendasNoFinanceiroTests(_VendasBase):
    """Insights e assistente passam a falar do lucro realizado, nao so da margem."""

    def test_insight_local_fala_do_lucro_das_vendas(self):
        self._vender(quantidade=3)

        insights = self.client.get("/api/finance/insights/").data["insights"]

        textos = " ".join(item["text"] for item in insights)
        self.assertIn("R$ 94,20 de lucro real", textos)
        self.assertIn("Bolo de cenoura puxou a fila", textos)

    def test_contexto_do_assistente_traz_vendas_e_margem_real(self):
        from apps.finance.assistant import build_context, format_context

        self._vender(quantidade=3)

        texto = format_context(build_context(self.business))

        self.assertIn("Bolo de cenoura: 3 unidade(s), faturamento R$ 180,00, lucro R$ 94,20", texto)
        # Margem real (31,40), nao preco menos custo (42,00).
        self.assertIn("margem real R$ 31,40", texto)
        self.assertNotIn("margem R$ 42,00", texto)


class LancamentoDaVendaTests(_VendasBase):
    def test_entrada_da_venda_nao_e_editada_nem_apagada_em_movimentacoes(self):
        self._vender(quantidade=1)
        lancamento = Transaction.objects.get()

        editar = self.client.patch(f"/api/transactions/{lancamento.id}/", {"amount": "1.00"}, format="json")
        apagar = self.client.delete(f"/api/transactions/{lancamento.id}/")

        self.assertEqual(editar.status_code, 400)
        self.assertEqual(apagar.status_code, 400)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.amount, Decimal("60.00"))


@override_settings(ANTHROPIC_API_KEY="")
class RecomendacaoComVendasTests(_VendasBase):
    def test_produto_de_margem_boa_sem_venda_recente_vira_recomendacao(self):
        from apps.marketing.models import MarketingCampaign

        # O bolo ja teve campanha: sem isso, a recomendacao de estreia vem antes
        # e, de proposito, o mesmo produto nao aparece duas vezes.
        MarketingCampaign.objects.create(
            business=self.business, product=self.bolo, prompt="post", channel="Instagram", goal="promocao"
        )
        brigadeiro = self._produto("Brigadeiro", price="3", cost="1", stock=50)
        self._vender(brigadeiro, quantidade=5)
        # Parado so conta para produto com mais de 30 dias de cadastro.
        Product.objects.filter(pk=self.bolo.pk).update(created_at=timezone.now() - timedelta(days=40))

        recomendacoes = self.client.get("/api/marketing/recommendations/").data["recommendations"]

        parado = [r for r in recomendacoes if r["title"] == "Tire da prateleira"]
        self.assertEqual(len(parado), 1)
        self.assertEqual(parado[0]["product_name"], "Bolo de cenoura")

    def test_sem_nenhuma_venda_nenhum_produto_e_tratado_como_parado(self):
        recomendacoes = self.client.get("/api/marketing/recommendations/").data["recommendations"]

        self.assertFalse(any(r["title"] == "Tire da prateleira" for r in recomendacoes))

    def test_produto_sem_estoque_nao_e_recomendado_para_divulgar(self):
        Product.objects.filter(pk=self.bolo.pk).update(stock=0)
        self._produto("Brigadeiro", price="3", cost="1", stock=50)

        recomendacoes = self.client.get("/api/marketing/recommendations/").data["recommendations"]

        divulgar = [r for r in recomendacoes if r["title"] in ("Estreie a divulgação", "Priorize o que rende")]
        self.assertTrue(divulgar)
        self.assertTrue(all(r["product_name"] != "Bolo de cenoura" for r in divulgar))
        # O brigadeiro nao e o de melhor margem: o texto nao pode dizer que e.
        self.assertNotIn("é o que mais rende", divulgar[0]["text"])
