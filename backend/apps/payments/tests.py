"""Testes das cobrancas PIX.

Tres pontos: o webhook (sem o segredo certo, qualquer um marcaria uma cobranca
como paga), a conciliacao com o financeiro (cobranca paga vira uma entrada, e
uma so, por mais que a Abacate Pay reenvie o evento) e o isolamento entre
negocios. A Abacate Pay nunca e chamada de verdade: `requests.request` fica
trocado por um mock em todos os testes.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.businesses.models import Business
from apps.finance.models import Transaction

from .models import Payment, PaymentEvent

SEGREDO = "segredo_teste"
WEBHOOK = "/api/payments/webhooks/abacatepay/"


def _resposta_abacate(status_code=200, corpo=None):
    """Resposta falsa do `requests` com o JSON dado."""
    resposta = Mock(status_code=status_code)
    resposta.json.return_value = corpo if corpo is not None else {}
    return resposta


# Valores fixos: um .env com a chave de verdade nao pode fazer a suite usar a
# conta da Abacate Pay nem mudar o segredo que o webhook espera.
@override_settings(ABACATE_PAY_API_KEY="abc_dev_teste", ABACATE_PAY_WEBHOOK_SECRET=SEGREDO)
class _PagamentosBase(TestCase):
    def setUp(self):
        # O contador do throttle vive no cache e o id do usuario se repete
        # entre testes: sem limpar, a suite inteira divide o mesmo limite.
        cache.clear()

        patcher = patch("apps.payments.services.requests.request")
        self.abacate = patcher.start()
        self.addCleanup(patcher.stop)

        self.admin, self.business, self.client = self._conta("admin@wageup.local", "admin")

    def _conta(self, email, role):
        User = get_user_model()
        user = User.objects.create_user(username=email, email=email, password="x")
        UserProfile.objects.create(user=user, role=role)
        business = Business.objects.create(owner=user, name=f"Negocio de {email}")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
        return user, business, cliente

    def _cobranca(self, business=None, **campos):
        dados = {
            "business": business or self.business,
            "amount": Decimal("80.00"),
            "provider_payment_id": "pix_char_1",
            "metadata": {"description": "Bolo de cenoura"},
        }
        dados.update(campos)
        return Payment.objects.create(**dados)


class CriarCobrancaTests(_PagamentosBase):
    def _gerar(self, **campos):
        corpo = {"amount": "25.90", "description": "Bolo de cenoura"}
        corpo.update(campos)
        return self.client.post("/api/payments/", corpo, format="json")

    def test_admin_gera_pix_e_guarda_o_codigo(self):
        self.abacate.return_value = _resposta_abacate(200, {"data": {
            "id": "pix_char_1",
            "brCode": "00020101021226",
            "brCodeBase64": "data:image/png;base64,AAAA",
            "expiresAt": "2026-10-08T15:00:00Z",
        }})

        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 201)
        cobranca = Payment.objects.get()
        self.assertEqual(cobranca.status, Payment.Status.PENDING)
        self.assertEqual(cobranca.business, self.business)
        self.assertEqual(cobranca.provider_payment_id, "pix_char_1")
        self.assertEqual(cobranca.metadata["brCode"], "00020101021226")
        self.assertEqual(resposta.data["metadata"]["brCodeBase64"], "data:image/png;base64,AAAA")

    def test_valor_vai_em_centavos_com_a_chave_e_o_id_da_cobranca(self):
        self.abacate.return_value = _resposta_abacate(200, {"data": {"id": "pix_char_1"}})

        self._gerar(amount="19.99")

        chamada = self.abacate.call_args
        self.assertEqual(chamada.args[:2], ("POST", "https://api.abacatepay.com/v2/transparents/create"))
        self.assertEqual(chamada.kwargs["headers"]["Authorization"], "Bearer abc_dev_teste")
        dados = chamada.kwargs["json"]["data"]
        self.assertEqual(dados["amount"], 1999)
        self.assertEqual(dados["metadata"], {"payment_id": str(Payment.objects.get().id)})

    def test_cliente_sem_cpf_e_celular_nao_vai_para_a_abacate_mas_fica_guardado(self):
        # A Abacate Pay responde 422 se o customer vier sem taxId e cellphone juntos.
        self.abacate.return_value = _resposta_abacate(200, {"data": {"id": "pix_char_1"}})

        self._gerar(customer_name="Maria Souza", customer_email="maria@exemplo.com")

        self.assertNotIn("customer", self.abacate.call_args.kwargs["json"]["data"])
        self.assertEqual(
            Payment.objects.get().metadata["customer"],
            {"name": "Maria Souza", "email": "maria@exemplo.com"},
        )

    def test_cliente_com_cpf_e_celular_vai_para_a_abacate(self):
        self.abacate.return_value = _resposta_abacate(200, {"data": {"id": "pix_char_1"}})

        self._gerar(customer_name="Maria Souza", customer_tax_id="12345678909", customer_cellphone="11999998888")

        self.assertEqual(
            self.abacate.call_args.kwargs["json"]["data"]["customer"],
            {"taxId": "12345678909", "cellphone": "11999998888", "name": "Maria Souza"},
        )

    def test_abacate_fora_do_ar_responde_502_e_marca_a_cobranca_como_falha(self):
        self.abacate.side_effect = requests.ConnectionError("conexao recusada")

        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 502)
        self.assertIn("Falha de conexao", resposta.data["detail"])
        cobranca = Payment.objects.get()
        self.assertEqual(cobranca.status, Payment.Status.FAILED)
        self.assertIn("conexao recusada", cobranca.metadata["error"])

    def test_recusa_da_abacate_chega_ao_usuario_com_o_motivo(self):
        self.abacate.return_value = _resposta_abacate(422, {"error": "Invalid taxId"})

        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 502)
        self.assertIn("Invalid taxId", resposta.data["detail"])
        self.assertEqual(Payment.objects.get().status, Payment.Status.FAILED)

    def test_resposta_que_nao_e_json_vira_502(self):
        resposta_html = Mock(status_code=502)
        resposta_html.json.side_effect = ValueError("nao e JSON")
        self.abacate.return_value = resposta_html

        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 502)
        self.assertIn("Resposta invalida", resposta.data["detail"])

    @override_settings(ABACATE_PAY_API_KEY="")
    def test_sem_chave_configurada_nao_chama_a_api(self):
        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 502)
        self.assertIn("ABACATE_PAY_API_KEY", resposta.data["detail"])
        self.abacate.assert_not_called()

    @override_settings(ABACATE_PAY_API_KEY="abc_dev—teste")
    def test_chave_com_travessao_explica_o_erro_em_vez_de_quebrar(self):
        # O hifen que vira travessao ao copiar a chave quebraria o cabecalho HTTP.
        resposta = self._gerar()

        self.assertEqual(resposta.status_code, 502)
        self.assertIn("travessao", resposta.data["detail"])
        self.abacate.assert_not_called()

    def test_valor_invalido_e_recusado_sem_criar_cobranca(self):
        resposta = self._gerar(amount="vinte reais")

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)
        self.abacate.assert_not_called()


class WebhookTests(_PagamentosBase):
    def setUp(self):
        super().setUp()
        self.cobranca = self._cobranca()

    def _evento(self, tipo="transparent.completed", event_id="log_1", segredo=SEGREDO, cobranca_id="pix_char_1"):
        url = WEBHOOK if segredo is None else f"{WEBHOOK}?webhookSecret={segredo}"
        corpo = {"id": event_id, "event": tipo, "data": {"transparent": {"id": cobranca_id}}}
        return APIClient().post(url, corpo, format="json")

    def _receitas(self):
        return Transaction.objects.filter(type=Transaction.TransactionType.INCOME)

    def test_segredo_errado_e_recusado_e_nada_muda(self):
        resposta = self._evento(segredo="chute")

        self.assertEqual(resposta.status_code, 401)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.PENDING)
        self.assertEqual(PaymentEvent.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_sem_segredo_na_url_e_recusado(self):
        resposta = self._evento(segredo=None)

        self.assertEqual(resposta.status_code, 401)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.PENDING)

    @override_settings(ABACATE_PAY_WEBHOOK_SECRET="", DEBUG=False)
    def test_sem_segredo_configurado_em_producao_fecha_a_rota(self):
        resposta = self._evento(segredo="")

        self.assertEqual(resposta.status_code, 503)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.PENDING)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_pagamento_confirmado_marca_pago_e_lanca_a_receita(self):
        resposta = self._evento()

        self.assertEqual(resposta.status_code, 201)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.PAID)
        receita = self._receitas().get()
        self.assertEqual(receita.business, self.business)
        self.assertEqual(receita.amount, Decimal("80.00"))
        self.assertEqual(receita.source, Transaction.Source.PIX)
        self.assertIn("Bolo de cenoura", receita.description)

    def test_evento_reenviado_nao_duplica_a_receita(self):
        self._evento()
        resposta = self._evento()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(self._receitas().count(), 1)

    def test_dois_eventos_de_pagamento_da_mesma_cobranca_lancam_uma_receita(self):
        self._evento(tipo="checkout.completed", event_id="log_1")
        self._evento(tipo="transparent.completed", event_id="log_2")

        self.assertEqual(PaymentEvent.objects.count(), 2)
        self.assertEqual(self._receitas().count(), 1)

    def test_estorno_lanca_a_saida_correspondente(self):
        self._evento(event_id="log_1")
        self._evento(tipo="transparent.refunded", event_id="log_2")

        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.REFUNDED)
        saida = Transaction.objects.get(type=Transaction.TransactionType.EXPENSE)
        self.assertEqual(saida.amount, Decimal("80.00"))
        self.assertIn("Estorno", saida.description)

    def test_estorno_de_cobranca_nunca_paga_nao_lanca_saida(self):
        self._evento(tipo="transparent.refunded")

        self.assertEqual(Transaction.objects.count(), 0)

    def test_evento_sem_id_e_recusado(self):
        resposta = self._evento(event_id="")

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(PaymentEvent.objects.count(), 0)

    def test_evento_de_cobranca_desconhecida_e_aceito_sem_lancar_nada(self):
        # Responder erro faria a Abacate Pay reentregar um evento que nunca vai casar.
        resposta = self._evento(cobranca_id="pix_char_de_outro_sistema")

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_tipo_de_evento_desconhecido_nao_muda_o_status(self):
        self._evento(tipo="transparent.created")

        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.PENDING)
        self.assertEqual(Transaction.objects.count(), 0)


class ConsultaDeStatusTests(_PagamentosBase):
    def setUp(self):
        super().setUp()
        self.cobranca = self._cobranca()

    def _consultar(self):
        return self.client.post(f"/api/payments/{self.cobranca.id}/check/")

    def test_pago_na_abacate_marca_pago_e_lanca_a_receita(self):
        self.abacate.return_value = _resposta_abacate(200, {"data": {"id": "pix_char_1", "status": "PAID"}})

        resposta = self._consultar()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["status"], Payment.Status.PAID)
        chamada = self.abacate.call_args
        self.assertEqual(chamada.args[:2], ("GET", "https://api.abacatepay.com/v2/transparents/check"))
        self.assertEqual(chamada.kwargs["params"], {"id": "pix_char_1"})
        self.assertEqual(Transaction.objects.filter(source=Transaction.Source.PIX).count(), 1)

    def test_consultar_de_novo_nao_duplica_a_receita(self):
        self.abacate.return_value = _resposta_abacate(200, {"data": {"status": "PAID"}})

        self._consultar()
        self._consultar()

        self.assertEqual(Transaction.objects.count(), 1)

    def test_webhook_e_consulta_juntos_lancam_uma_receita(self):
        APIClient().post(
            f"{WEBHOOK}?webhookSecret={SEGREDO}",
            {"id": "log_1", "event": "transparent.completed", "data": {"transparent": {"id": "pix_char_1"}}},
            format="json",
        )
        self.abacate.return_value = _resposta_abacate(200, {"data": {"status": "PAID"}})

        self._consultar()

        self.assertEqual(Transaction.objects.count(), 1)

    def test_cobranca_paga_nao_volta_a_expirada(self):
        self.cobranca.status = Payment.Status.PAID
        self.cobranca.save()
        self.abacate.return_value = _resposta_abacate(200, {"data": {"status": "EXPIRED"}})

        resposta = self._consultar()

        self.assertEqual(resposta.data["status"], Payment.Status.PAID)

    def test_expirada_na_abacate_marca_expirada_sem_lancar_nada(self):
        self.abacate.return_value = _resposta_abacate(
            200, {"data": {"status": "EXPIRED", "expiresAt": "2026-10-08T15:00:00Z"}}
        )

        resposta = self._consultar()

        self.assertEqual(resposta.data["status"], Payment.Status.EXPIRED)
        self.assertEqual(resposta.data["metadata"]["expiresAt"], "2026-10-08T15:00:00Z")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_abacate_sem_responder_devolve_502_e_mantem_o_status(self):
        self.abacate.side_effect = requests.Timeout()

        resposta = self._consultar()

        self.assertEqual(resposta.status_code, 502)
        self.assertIn("nao respondeu em tempo", resposta.data["detail"])
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, Payment.Status.PENDING)

    def test_cobranca_que_falhou_ao_gerar_nao_consulta_a_abacate(self):
        self.cobranca.provider_payment_id = ""
        self.cobranca.status = Payment.Status.FAILED
        self.cobranca.save()

        resposta = self._consultar()

        self.assertEqual(resposta.status_code, 200)
        self.abacate.assert_not_called()


class ResumoTests(_PagamentosBase):
    def test_soma_recebido_e_a_receber(self):
        self._cobranca(amount=Decimal("100.00"), status=Payment.Status.PAID)
        self._cobranca(amount=Decimal("50.50"), status=Payment.Status.PAID)
        self._cobranca(amount=Decimal("30.00"), status=Payment.Status.PENDING)
        self._cobranca(amount=Decimal("999.00"), status=Payment.Status.FAILED)
        antiga = self._cobranca(amount=Decimal("20.00"), status=Payment.Status.PAID)
        # created_at e auto_now_add: so um update muda a data depois de criado.
        Payment.objects.filter(pk=antiga.pk).update(created_at=timezone.now() - timedelta(days=40))

        resumo = self.client.get("/api/payments/summary/").data

        self.assertEqual(resumo["received_total"], 170.50)
        self.assertEqual(resumo["received_this_month"], 150.50)
        self.assertEqual(resumo["pending_total"], 30.00)
        self.assertEqual(resumo["paid_count"], 3)
        self.assertEqual(resumo["pending_count"], 1)

    def test_cobranca_de_outro_negocio_fica_fora_do_resumo(self):
        _, outro_negocio, _ = self._conta("outro@wageup.local", "admin")
        self._cobranca(business=outro_negocio, amount=Decimal("500.00"), status=Payment.Status.PAID)

        resumo = self.client.get("/api/payments/summary/").data

        self.assertEqual(resumo["received_total"], 0)
        self.assertEqual(resumo["paid_count"], 0)


class PermissaoEIsolamentoTests(_PagamentosBase):
    def test_member_nao_gera_pix(self):
        _, _, member = self._conta("mei@wageup.local", "member")

        resposta = member.post("/api/payments/", {"amount": "10.00"}, format="json")

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Payment.objects.count(), 0)
        self.abacate.assert_not_called()

    def test_member_nao_lista_cobrancas_nem_resumo(self):
        _, _, member = self._conta("mei@wageup.local", "member")

        self.assertEqual(member.get("/api/payments/").status_code, 403)
        self.assertEqual(member.get("/api/payments/summary/").status_code, 403)

    def test_sem_login_nao_acessa(self):
        anonimo = APIClient()

        self.assertEqual(anonimo.get("/api/payments/").status_code, 401)
        self.assertEqual(anonimo.post("/api/payments/", {"amount": "10.00"}, format="json").status_code, 401)
        self.abacate.assert_not_called()

    def test_cobranca_de_outro_negocio_nao_aparece_nem_abre(self):
        _, outro_negocio, _ = self._conta("outro@wageup.local", "admin")
        alheia = self._cobranca(business=outro_negocio, provider_payment_id="pix_char_alheio")
        minha = self._cobranca(provider_payment_id="pix_char_meu")

        lista = self.client.get("/api/payments/").data
        ids = [item["id"] for item in (lista["results"] if isinstance(lista, dict) else lista)]

        self.assertEqual(ids, [str(minha.id)])
        self.assertEqual(self.client.get(f"/api/payments/{alheia.id}/").status_code, 404)

    def test_nao_consulta_status_da_cobranca_de_outro_negocio(self):
        _, outro_negocio, _ = self._conta("outro@wageup.local", "admin")
        alheia = self._cobranca(business=outro_negocio)

        resposta = self.client.post(f"/api/payments/{alheia.id}/check/")

        self.assertEqual(resposta.status_code, 404)
        self.abacate.assert_not_called()

    def test_nao_apaga_cobranca_de_outro_negocio(self):
        _, outro_negocio, _ = self._conta("outro@wageup.local", "admin")
        alheia = self._cobranca(business=outro_negocio)

        resposta = self.client.delete(f"/api/payments/{alheia.id}/")

        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(Payment.objects.filter(pk=alheia.pk).exists())
