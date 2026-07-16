# WageUp — O que a plataforma faz hoje

> Documento de **funcionalidades** (visão de produto). Para arquitetura técnica, ver [`CLAUDE.md`](CLAUDE.md).
> Última atualização: 2026-06-07.

Este arquivo existe para que a gente sempre saiba, em linguagem simples, **o que já está pronto, o que está pela metade e o que ainda não existe**. Sempre que uma feature for concluída ou alterada, atualize esta lista.

---

## 1. Cadastro e login

- [x] Criar conta com e-mail e senha
- [x] Login com e-mail e senha (token de autenticação)
- [x] Login com conta Google (Google Identity Services no front + verificação do token no back)
- [x] Logout
- [x] Cada conta nova ganha automaticamente um "negócio" (`Business`) vinculado a ela — é o que permite isolar os dados de cada usuário
- [x] Onboarding inicial (tela para o usuário preencher nome do negócio antes de usar a plataforma)

**Papéis de usuário:**
- **admin** — definido pela lista de e-mails em `WAGEUP_ADMIN_EMAILS`. Tem acesso ao módulo financeiro completo (transações + cobranças PIX).
- **member** — acesso a produtos, marketing com IA e onboarding, mas **sem** o módulo financeiro.

## 2. Catálogo de produtos

- [x] Cadastrar produto (nome, categoria, custo, preço, estoque)
- [x] Listar, editar e remover produtos
- [x] Dados isolados por negócio (um usuário nunca vê produtos de outro)

## 3. Módulo financeiro (somente admin)

- [x] Lançar transações manuais de **entrada** (receita) e **saída** (despesa)
- [x] Listar histórico de transações
- [x] Dashboard com indicadores (somatório de entradas/saídas, gráfico)

## 4. Cobranças via PIX (Abacate Pay) — somente admin

- [x] Gerar cobrança PIX (QR Code + código "copia e cola") através da API da Abacate Pay
- [x] Registrar a cobrança localmente (`Payment`) com status `pending` / `paid` / `failed` / `refunded`
- [x] Anexar dados do cliente (nome, e-mail, CPF/CNPJ, celular) à cobrança — **a Abacate Pay exige CPF/CNPJ e celular juntos**; se um dos dois faltar, a cobrança é gerada sem os dados do cliente (regra ajustada em 2026-07-15; antes disso a API retornava erro 422)
- [x] Lista de "Cobranças recentes" na tela de PIX, com badge de status, botão para reexibir o QR Code e atualização manual de status
- [x] Webhook (`/api/payments/webhook/abacatepay/`) para receber atualizações automáticas de status (pago, reembolsado, contestado) e atualizar o registro local
- [x] Consolidação de recebíveis — painel na Visão geral com total recebido, recebido no mês e valor a receber, agregado a partir das cobranças (`GET /api/payments/summary/`)

## 5. Marketing com Inteligência Artificial

- [x] Gerar texto de campanha de marketing a partir de um prompt, canal (ex.: Instagram, WhatsApp) e objetivo (ex.: aumentar vendas)
- [x] Integração real com a Anthropic (modelo Claude Haiku) — com fallback local (texto de demonstração) quando não há `ANTHROPIC_API_KEY` configurada
- [x] Histórico de campanhas geradas, vinculado ao negócio e (opcionalmente) a um produto
- [ ] Geração de imagens para campanhas (campo `image_url` existe no modelo, mas não é preenchido automaticamente ainda)
- [ ] Recomendações automáticas de ações de marketing baseadas no desempenho do negócio (ainda não implementado — está no escopo do TCC)

## 6. Visão geral / Dashboard

- [x] Tela inicial com resumo do negócio (produtos cadastrados, transações recentes, indicadores financeiros para admins)
- [ ] Insights e recomendações geradas por IA com base nos dados financeiros e de produtos (ainda não implementado — está no escopo do TCC)

## 7. Administração e visibilidade de dados

- [x] Django Admin (`/admin/`) configurado para todos os modelos (contas, negócios, produtos, transações, pagamentos, campanhas) com filtros e busca — útil para inspecionar o banco de dados sem precisar de SQL
- [x] Conta de admin do Guilherme (`guilherme.maiellaroo@gmail.com`) com `role=admin`, liberando o módulo financeiro

---

## O que ainda falta (do escopo do TCC)

Com base no `Escopo TCC.pdf`, os itens abaixo ainda não foram implementados:

1. **Insights/recomendações por IA** — a IA hoje só gera texto de campanha sob demanda; falta cruzar dados financeiros + produtos para sugerir ações automaticamente.
2. **Geração de imagens para campanhas de marketing**.
3. **Recomendações automáticas de ações de marketing** baseadas no desempenho do negócio.

---

## Como testar cada feature manualmente

| Feature | Como testar |
|---|---|
| Cadastro/login | Acessar a landing page → "Entrar" → criar conta ou usar Google |
| Onboarding | Após o primeiro login, preencher nome do negócio |
| Produtos | Menu "Produtos" → cadastrar/editar/remover |
| Financeiro | Login como admin → aba "Financeiro" → lançar transação |
| PIX | Login como admin → aba "Financeiro" → "Cobrança PIX" → preencher e gerar |
| Marketing IA | Menu "Marketing" → preencher prompt/canal/objetivo → gerar campanha |
| Admin/banco de dados | Acessar `/admin/` logado como superusuário Django |
