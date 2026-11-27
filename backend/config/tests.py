from django.test import SimpleTestCase


class PaginasDoSiteTests(SimpleTestCase):
    """Home e paginas de modulo servem o mesmo HTML; o site.js escolhe a pagina."""

    PAGINAS = [
        "/", "/vendas", "/financeiro", "/pix", "/marketing", "/assistente",
        "/para-quem", "/acessibilidade", "/perguntas",
    ]

    def test_cada_pagina_serve_o_html_com_os_assets_versionados(self):
        for caminho in self.PAGINAS:
            with self.subTest(caminho=caminho):
                resposta = self.client.get(caminho)
                self.assertEqual(resposta.status_code, 200)
                html = resposta.content.decode()
                self.assertIn('data-page="pix"', html)
                self.assertIn('src="site.js?v=', html)
                self.assertIn('href="styles.css?v=', html)

    def test_barra_no_fim_redireciona_sem_a_barra(self):
        # Os assets sao relativos: em /pix/ o navegador buscaria /pix/styles.css.
        resposta = self.client.get("/pix/")
        self.assertEqual(resposta.status_code, 301)
        self.assertEqual(resposta["Location"], "/pix")

    def test_caminho_desconhecido_nao_vira_pagina(self):
        self.assertEqual(self.client.get("/qualquer-coisa").status_code, 404)

    def test_site_js_e_servido(self):
        resposta = self.client.get("/site.js")
        self.assertEqual(resposta.status_code, 200)

    def test_asset_versionado_fica_no_cache_do_navegador(self):
        # Com ?v= o arquivo nunca muda sob a mesma URL: o navegador guarda.
        resposta = self.client.get("/app.js?v=123")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("immutable", resposta["Cache-Control"])

    def test_asset_sem_versao_nao_fica_guardado_para_sempre(self):
        resposta = self.client.get("/app.js")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("immutable", resposta.get("Cache-Control", ""))
