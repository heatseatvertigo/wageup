# WageUp — O que a plataforma faz hoje

> Documento de **funcionalidades** (visão de produto). Para arquitetura técnica, ver [`CLAUDE.md`](CLAUDE.md).
> Última atualização: 2026-09-05.

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
- [x] Filtros por tipo e por período, com totais do recorte
- [x] Cada lançamento mostra de onde veio: manual, cobrança PIX ou extrato importado

### Importação de extrato bancário

- [x] Botão "Importar extrato" na tela de Movimentações — o usuário anexa o arquivo e a plataforma lê os lançamentos
- [x] Formato **OFX**, que os bancos grandes exportam no internet banking
- [x] **Tela de conferência antes de gravar**: o usuário desmarca o que não quer, corrige a descrição e o tipo, e só então confirma. Extrato traz transferência entre contas próprias, que não é receita nem despesa — importar direto sujaria os totais
- [x] **Reimportar o mesmo extrato não duplica nada.** Cada lançamento guarda o identificador que o banco atribui (FITID); o que já existe vem desmarcado e marcado como "Já importado". Sem FITID, o identificador vem de uma impressão digital do conteúdo, que continua distinguindo dois lançamentos iguais no mesmo dia
- [x] **O arquivo nunca é gravado.** É lido em memória e descartado; ficam só os lançamentos confirmados e um hash, usado para avisar quando o mesmo arquivo é reenviado. Extrato bancário é dado sensível e a funcionalidade não precisa guardá-lo
- [x] Limite de 5 MB por arquivo, e arquivo ilegível responde com explicação em vez de erro 500
- [ ] Formatos **CSV** e **PDF** — a estrutura está pronta para recebê-los, falta o leitor de cada um

### Conexão direta com o banco — apenas explicativa

- [x] Botão "Integre com seu banco" em Movimentações, com selo **Em breve**, abrindo uma tela que explica como a conexão automática funcionaria: escolher o banco, autorizar dentro do próprio banco, e os lançamentos entrando sozinhos na tela de conferência
- [x] A tela deixa claro que a senha do banco nunca passaria pela plataforma
- [ ] **A integração em si não existe.** Não há backend, nem chamada de API, nem contrato com provedor. A tela serve para apresentar a próxima etapa do produto — o logo do Nubank é o oficial; os demais bancos e o provedor aparecem como placeholder (sigla em círculo), até os arquivos serem adicionados ao projeto

## 4. Cobranças via PIX (Abacate Pay) — somente admin

- [x] Gerar cobrança PIX (QR Code + código "copia e cola") através da API da Abacate Pay
- [x] Registrar a cobrança localmente (`Payment`) com status `pending` / `paid` / `failed` / `refunded`
- [x] Anexar dados do cliente (nome, e-mail, CPF/CNPJ, celular) à cobrança — **a Abacate Pay exige CPF/CNPJ e celular juntos**; se um dos dois faltar, a cobrança é gerada sem os dados do cliente (regra ajustada em 2026-07-15; antes disso a API retornava erro 422)
- [x] Lista de "Cobranças recentes" na tela de PIX, com badge de status, botão para reexibir o QR Code e atualização manual de status
- [x] Webhook (`/api/payments/webhooks/abacatepay/`) para receber atualizações automáticas de status (pago, reembolsado, contestado) e atualizar o registro local
- [x] Consolidação de recebíveis — painel na Visão geral com total recebido, recebido no mês e valor a receber, agregado a partir das cobranças (`GET /api/payments/summary/`)

## 5. Marketing com Inteligência Artificial

- [x] Gerar texto de campanha de marketing a partir de um prompt, canal (ex.: Instagram, WhatsApp) e objetivo (ex.: aumentar vendas)
- [x] Integração real com a Anthropic (modelo Claude Haiku) — com fallback local (texto de demonstração) quando não há `ANTHROPIC_API_KEY` configurada
- [x] Histórico de campanhas geradas, vinculado ao negócio e (opcionalmente) a um produto
- [ ] Geração de imagens para campanhas (campo `image_url` existe no modelo, mas não é preenchido automaticamente ainda)
- [ ] Recomendações automáticas de ações de marketing baseadas no desempenho do negócio (ainda não implementado — está no escopo do TCC)

## 6. Visão geral / Dashboard

- [x] Tela inicial com resumo do negócio (produtos cadastrados, transações recentes, indicadores financeiros para admins)
- [x] Insights por IA com base nos dados financeiros, recebíveis e produtos — botão "Gerar insights com IA" na Visão geral (`GET /api/finance/insights/`), com fallback local por regras quando não há `ANTHROPIC_API_KEY` ou a chamada à IA falha

## 7. Assistente financeiro (somente admin)

- [x] Chat em tela cheia onde o usuário pergunta sobre os próprios números ("quanto entrou este mês?", "qual produto tem a melhor margem?")
- [x] Todo número é calculado em Python antes de chegar ao modelo — o modelo escreve o texto, mas não faz a conta. Isso evita valor inventado
- [x] O assistente enxerga transações, cobranças PIX e produtos do negócio
- [x] Histórico de conversas salvo no banco (`AssistantConversation` / `AssistantMessage`), não no navegador. Além de sobreviver ao recarregar a página, impede que o cliente forje o que foi dito antes
- [x] Listar, abrir e apagar conversas anteriores
- [x] Provedores em cascata: DeepSeek (`DEEPSEEK_API_KEY`), Anthropic como alternativa (`ANTHROPIC_API_KEY`) e, sem nenhuma chave, uma resposta local avisando que não está configurado

Endpoints: `POST /api/finance/assistant/`, `GET|POST /api/finance/assistant/conversations/`, `GET|DELETE /api/finance/assistant/conversations/<id>/`.

## 8. Administração e visibilidade de dados

- [x] Django Admin (`/admin/`) configurado para todos os modelos (contas, negócios, produtos, transações, pagamentos, campanhas) com filtros e busca — útil para inspecionar o banco de dados sem precisar de SQL
- [x] Conta de admin do Guilherme (`guilherme.maiellaroo@gmail.com`) com `role=admin`, liberando o módulo financeiro

## 9. Segurança e operação

- [x] API fechada por padrão: uma rota que esqueça de declarar permissão fica inacessível, não pública. Só registro, login, webhook e health check são abertos, e de forma explícita
- [x] Limite de requisições (throttling): 60/hora nas rotas que chamam IA (cada chamada custa dinheiro), 10/min em login e registro (contra força bruta), além do limite geral por usuário
- [x] Em produção: HTTPS obrigatório, HSTS, cookies com `Secure`, API navegável do DRF desligada e recusa de subir com a `SECRET_KEY` de exemplo
- [x] Webhook da Abacate Pay só funciona com segredo configurado, comparado em tempo constante. Sem o segredo, qualquer um poderia marcar uma cobrança como paga
- [x] Logs da aplicação aparecem na saída do servidor (antes se perdiam)
- [x] Primeiros testes automatizados: 15 casos cobrindo a leitura de OFX e a importação ponta a ponta
- [ ] Testes dos demais módulos (contas, produtos, pagamentos, marketing) — ainda não existem

---

## O que ainda falta (do escopo do TCC)

Com base no `Escopo TCC.pdf`, os itens abaixo ainda não foram implementados:

1. **Recomendações automáticas de ações de marketing** baseadas no desempenho do negócio.
2. **Geração de imagens para campanhas de marketing**.

Fora do escopo do PDF, mas pendente: **testes automatizados dos demais módulos** e os leitores de extrato em **CSV** e **PDF**.

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
| Importar extrato | Login como admin → "Movimentações" → "Importar extrato" → anexar um `.ofx` → conferir a lista → "Importar". Reenviar o mesmo arquivo deve trazer tudo desmarcado como "Já importado" |
| Assistente financeiro | Login como admin → abrir o chat → perguntar sobre os números; recarregar a página e conferir que a conversa continua lá |
| Admin/banco de dados | Acessar `/admin/` logado como superusuário Django |
