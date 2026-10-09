# WageUp — O que a plataforma faz hoje

> Documento de **funcionalidades** (visão de produto). Para arquitetura técnica, ver [`CLAUDE.md`](CLAUDE.md).
> Última atualização: 2026-10-08.

Este arquivo existe para que a gente sempre saiba, em linguagem simples, **o que já está pronto, o que está pela metade e o que ainda não existe**. Sempre que uma feature for concluída ou alterada, atualize esta lista.

---

## 1. Cadastro e login

- [x] Criar conta com e-mail e senha
- [x] Login com e-mail e senha (token de autenticação)
- [x] Login com conta Google (Google Identity Services no front + verificação do token no back)
- [x] Logout
- [x] Cada conta nova ganha automaticamente um "negócio" (`Business`) vinculado a ela — é o que permite isolar os dados de cada usuário
- [x] Onboarding inicial (tela para o usuário preencher nome do negócio antes de usar a plataforma)

**Recuperação de senha:**
- [x] Pedido do link pela API (`POST /api/auth/password-reset/`) — o e-mail chega com um link válido por 2 horas
- [x] Troca da senha pelo link (`POST /api/auth/password-reset/confirm/`)
- [x] O link deixa de valer assim que a senha é trocada, e a sessão antiga é derrubada junto — quem redefine a senha costuma estar expulsando um invasor
- [x] A resposta é a mesma existindo a conta ou não, para a rota não virar um verificador de quem tem cadastro na plataforma
- [x] **Entrega pelo Resend** (API HTTP): `RESEND_API_KEY` liga o envio de verdade. Testado de ponta a ponta — pedido, e-mail recebido, link, senha nova
- [x] Em desenvolvimento, sem chave nenhuma, o e-mail é impresso no terminal do `runserver`: dá para testar o fluxo inteiro sem configurar provedor
- [x] Link "Esqueci minha senha" na tela de login, com tela de pedido e tela de nova senha
- [x] O link do e-mail abre direto a tela de nova senha; `uid` e `token` saem da barra de endereço assim que são lidos, para não ficarem no histórico do navegador
- [x] Confirmação da senha em dois campos, conferida antes de chamar a API
- [ ] **Variáveis do Resend em produção** — falta preencher `RESEND_API_KEY` e `DEFAULT_FROM_EMAIL` no Render
- [ ] **Domínio verificado no Resend** — sem isso o provedor só entrega para o e-mail da própria conta, então o link não chega a outros usuários

**Papéis de usuário:**
- **admin** — definido pela lista de e-mails em `WAGEUP_ADMIN_EMAILS`. Tem acesso ao módulo financeiro completo (transações + cobranças PIX).
- **member** — acesso a produtos, marketing com IA e onboarding, mas **sem** o módulo financeiro.

## 2. Catálogo de produtos

- [x] Cadastrar, editar e remover produto, numa tela única com nome, categoria, código, unidade (unidade, quilo, litro, metro, pacote, serviço) e descrição
- [x] **Foto do produto**, reduzida no próprio navegador antes de subir e guardada no banco — o disco do servidor é apagado a cada deploy, então arquivo salvo lá sumiria
- [x] **Cálculo de margem real**, não só preço menos custo. Entram outros custos por unidade (embalagem, frete) e os percentuais de taxa de cartão/PIX e imposto, que saem do mesmo bolso e não aparecem na conta simples
- [x] O painel de cálculo responde **enquanto o usuário digita**: quanto sobra em reais, quanto isso representa do preço, markup sobre o custo e as taxas em reais
- [x] **Preço sugerido para uma margem alvo** — "quero ganhar 30%, quanto preciso cobrar?". Quando taxas e alvo somam 100% ou mais, a tela diz que nenhum preço fecha a conta em vez de mostrar um número absurdo
- [x] Margem negativa aparece como **Prejuízo**, com cor e rótulo — nunca só a cor
- [x] Estoque mínimo, com aviso de **estoque baixo** na grade
- [x] Produto **ativo ou inativo**, para tirar do catálogo sem apagar o histórico
- [x] Grade com foto, preço, margem e estoque; clicar abre a edição
- [x] Dados isolados por negócio (um usuário nunca vê produtos de outro)
- [x] Lucro realizado por produto, a partir das vendas (ver abaixo)
- [ ] Giro de estoque (quantos dias o estoque dura no ritmo atual de vendas)

### Vendas (admin e membro)

A venda é o que liga o catálogo ao estoque e ao financeiro. Antes dela, a margem calculada no produto nunca virava lucro de verdade e vender não baixava o estoque.

- [x] Tela **Vendas** no menu, para admin e membro: produto, quantidade, preço por unidade (dá para registrar desconto ou preço combinado), forma de pagamento e data
- [x] Prévia do total e do **lucro real** enquanto o usuário preenche; quem grava a conta é o servidor, com custo, taxa e imposto do produto no banco
- [x] A venda **baixa o estoque**. Pedir mais do que há em estoque bloqueia a venda com "Só há N em estoque"; duas vendas ao mesmo tempo não levam o estoque abaixo de zero
- [x] Produto com unidade **serviço** não controla estoque
- [x] A venda **lança a entrada no financeiro**, com origem "Venda". Essa entrada não pode ser editada nem apagada em Movimentações: desfaz-se cancelando a venda
- [x] Os valores do produto são **copiados no momento da venda**: mudar preço ou custo depois não muda o lucro de uma venda antiga
- [x] **Cancelar a venda** devolve o estoque e tira a entrada do financeiro. Não existe editar nem apagar venda
- [x] Resumo do mês: vendido, lucro real e unidades; detalhe de cada venda mostrando de onde sai o lucro (total, custo, taxa e imposto)
- [x] **Cobrança PIX de um produto vira venda quando é paga** (ver PIX)
- [x] Venda e movimentação não se misturam: em "Nova movimentação", escolher Entrada mostra um aviso com atalho para registrar a venda, que é o caminho que baixa estoque e calcula lucro. A movimentação manual fica para o que não é venda de produto: aluguel, insumo, conta de luz, aporte

Endpoints: `GET|POST /api/sales/?month=AAAA-MM`, `POST /api/sales/<id>/cancel/`, `GET /api/sales/summary/?month=AAAA-MM`.

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
- [x] **O que já foi lançado na plataforma não entra de novo.** Venda, PIX e lançamento manual não têm FITID, mas o banco mostra o mesmo dinheiro no extrato. Uma linha com mesmo tipo, mesmo valor e data a até um dia de distância de algo já lançado vem desmarcada, com "Já lançado: Venda" e o que ela parece. Cada lançamento cobre uma linha só, e quem decide é o usuário. Venda no cartão, que cai dias depois e com a taxa descontada, não é reconhecida
- [x] **O arquivo nunca é gravado.** É lido em memória e descartado; ficam só os lançamentos confirmados e um hash, usado para avisar quando o mesmo arquivo é reenviado. Extrato bancário é dado sensível e a funcionalidade não precisa guardá-lo
- [x] Limite de 5 MB por arquivo, e arquivo ilegível responde com explicação em vez de erro 500
- [ ] Formatos **CSV** e **PDF** — a estrutura está pronta para recebê-los, falta o leitor de cada um

### Conexão direta com o banco — apenas explicativa

- [x] Botão "Integre com seu banco" em Movimentações, com selo **Em breve**, abrindo uma tela marcada como **Protótipo** que explica como a conexão automática funcionaria: escolher o banco, autorizar dentro do próprio banco, e os lançamentos entrando sozinhos na tela de conferência
- [x] A tela deixa claro que a senha do banco nunca passaria pela plataforma
- [x] Aviso dentro da tela: a conexão ainda não existe, o caminho hoje é importar o extrato, e os logos são ilustrativos, sem parceria com os bancos nem com a Pluggy
- [ ] **A integração em si não existe.** Não há backend, nem chamada de API, nem contrato com provedor. A tela serve para apresentar a próxima etapa do produto — os logos dos oito bancos e o da Pluggy são os oficiais, usados de forma ilustrativa — não existe parceria nem contrato com nenhum deles

## 4. Cobranças via PIX (Abacate Pay) — somente admin

- [x] Gerar cobrança PIX (QR Code + código "copia e cola") através da API da Abacate Pay
- [x] Registrar a cobrança localmente (`Payment`) com status `pending` / `paid` / `failed` / `refunded`
- [x] Anexar dados do cliente (nome, e-mail, CPF/CNPJ, celular) à cobrança — **a Abacate Pay exige CPF/CNPJ e celular juntos**; se um dos dois faltar, a cobrança é gerada sem os dados do cliente (regra ajustada em 2026-07-15; antes disso a API retornava erro 422)
- [x] Lista de "Cobranças recentes" na tela de PIX, com badge de status, botão para reexibir o QR Code e atualização manual de status
- [x] Webhook (`/api/payments/webhooks/abacatepay/`) para receber atualizações automáticas de status (pago, reembolsado, contestado) e atualizar o registro local
- [x] **Cobrança de um produto do catálogo**: escolher o produto preenche descrição e valor e pede a quantidade. O estoque é conferido ao gerar o PIX; quando a cobrança é paga (webhook ou consulta), ela vira uma venda, baixa o estoque e reaproveita a entrada do PIX no financeiro — uma venda só, mesmo que webhook e consulta cheguem juntos. Estorno cancela a venda e devolve o estoque
- [x] A API recusa cobrança de valor zero ou negativo, mesmo chamada fora da tela
- [x] Consolidação de recebíveis — painel na Visão geral com total recebido, recebido no mês e valor a receber, agregado a partir das cobranças (`GET /api/payments/summary/`)

## 5. Marketing com Inteligência Artificial

- [x] Chat de marketing com pedido livre (post, campanha, legenda, ideias de vídeo, mensagem para clientes), no mesmo formato do assistente financeiro, com histórico de conversas
- [x] A IA conhece o catálogo e a margem real de cada produto; o produto e o canal saem do próprio pedido
- [x] Provedores em cascata, como no assistente financeiro: DeepSeek (`DEEPSEEK_API_KEY`), Anthropic como alternativa (`ANTHROPIC_API_KEY`) e, sem nenhuma chave ou com as duas fora do ar, uma campanha local montada a partir do assunto do pedido
- [x] Os números que vão para a IA saem do produto no banco (preço, custo e **margem real**, com embalagem, frete, taxa e imposto descontados), não do que o navegador mandou. O prompt ainda avisa a IA para não sugerir desconto maior que a margem
- [x] Histórico de campanhas geradas, vinculado ao negócio e ao produto
- [x] **Recomendações automáticas de ação** (`GET /api/marketing/recommendations/`): devolve o que divulgar em seguida, na ordem produto em prejuízo (revisar preço antes) → produto de margem alta nunca divulgado → produto com estoque baixo (repor antes) → melhor margem do catálogo. Cada item já traz produto, canal e objetivo resolvidos
- [x] Sem `ANTHROPIC_API_KEY`, ou se a chamada falhar, as recomendações saem de regras locais sobre os mesmos números
- [x] **As recomendações aparecem como sugestões no chat de marketing**: cada uma vira um pedido pronto. Produto em prejuízo vira pergunta sobre preço, produto com estoque baixo vira mensagem para clientes, o resto vira pedido de campanha
- [x] Recomendação de **produto parado**: margem boa, tem estoque e não vendeu nos últimos 30 dias (só vale quando o negócio registra vendas)
- [x] Produto sem estoque nunca é recomendado para divulgar
- [x] **Geração da imagem da campanha**: sai junto com o texto, a partir da "ideia de imagem" que a própria campanha escreveu — texto e imagem falam da mesma coisa
- [x] Cloudflare Workers AI (FLUX.1-schnell) quando há `CLOUDFLARE_ACCOUNT_ID` e `CLOUDFLARE_API_TOKEN`; o plano free dá ~500 imagens de 1024x1024 por dia
- [x] Pollinations.ai como alternativa sem chave, ligada por `MARKETING_IMAGE_FALLBACK`. Opt-in de propósito: não pede chave, mas demora e põe marca d'água
- [x] Sem provedor nenhum, a campanha sai só com o texto — a geração nunca derruba o que já foi escrito
- [x] A imagem fica no banco (`CampaignImage`), como a foto de produto: o disco do Render é efêmero. Rota autenticada e filtrada por negócio. O FLUX sai sempre em 1024x1024 e o JPEG dá por volta de 540 KB, então o teto aqui é 1 MB (a foto de produto, que chega reduzida pelo navegador, para em 400 KB)

## 6. Visão geral / Dashboard

- [x] Tela inicial com resumo do negócio (produtos cadastrados, transações recentes, indicadores financeiros para admins)
- [x] Insights por IA com base nos dados financeiros, recebíveis e produtos (`GET /api/finance/insights/`), só admin, com fallback local por regras quando não há `ANTHROPIC_API_KEY` ou a chamada à IA falha
- [x] Painel **"O que os números dizem"** com os insights, incluindo o lucro das vendas do mês. A IA só é chamada de novo quando os dados mudaram, ou pelo botão Atualizar
- [x] Painel **Lucro por produto no mês**, a partir das vendas, para admin e membro. Acompanha o mês do calendário
- [x] Para o membro, a visão geral mostra só o lucro por produto: os cards, o calendário e o gráfico leem o financeiro, que é só do admin, e mostravam zeros

## 7. Assistente financeiro (somente admin)

- [x] Chat em tela cheia onde o usuário pergunta sobre os próprios números ("quanto entrou este mês?", "qual produto tem a melhor margem?")
- [x] Todo número é calculado em Python antes de chegar ao modelo — o modelo escreve o texto, mas não faz a conta. Isso evita valor inventado
- [x] O assistente enxerga transações, cobranças PIX e produtos do negócio
- [x] Histórico de conversas salvo no banco (`AssistantConversation` / `AssistantMessage`), não no navegador. Além de sobreviver ao recarregar a página, impede que o cliente forje o que foi dito antes
- [x] Listar, abrir e apagar conversas anteriores
- [x] Provedores em cascata: DeepSeek (`DEEPSEEK_API_KEY`), Anthropic como alternativa (`ANTHROPIC_API_KEY`) e, sem nenhuma chave, uma resposta local avisando que não está configurado

Endpoints: `POST /api/finance/assistant/`, `GET|POST /api/finance/assistant/conversations/`, `GET|DELETE /api/finance/assistant/conversations/<id>/`.

## 8. Página inicial (visitante)

- [x] Landing page servida na raiz, com a apresentação da plataforma e o caminho para entrar ou criar conta
- [x] **Demo de PIX no topo**: QR code, status "aguardando" pulsando e um botão que simula o pagamento — mostra o produto funcionando antes do cadastro
- [x] **Calculadora de margem** aberta ao visitante: a mesma conta do cadastro de produtos, sem precisar de conta
- [x] Faixa de números com contadores animados e um FAQ
- [x] Animações só de `opacity` e `transform` (GSAP + ScrollTrigger); com `prefers-reduced-motion` o movimento decorativo desliga e as interações continuam

---

## 9. Administração e visibilidade de dados

- [x] Django Admin (`/admin/`) configurado para todos os modelos (contas, negócios, produtos, transações, pagamentos, campanhas) com filtros e busca — útil para inspecionar o banco de dados sem precisar de SQL
- [x] Conta de admin do Guilherme (`guilherme.maiellaroo@gmail.com`) com `role=admin`, liberando o módulo financeiro

## 10. Segurança e operação

- [x] API fechada por padrão: uma rota que esqueça de declarar permissão fica inacessível, não pública. Só registro, login, webhook e health check são abertos, e de forma explícita
- [x] Limite de requisições (throttling): 60/hora nas rotas que chamam IA (cada chamada custa dinheiro), 10/min em login e registro (contra força bruta), além do limite geral por usuário
- [x] Em produção: HTTPS obrigatório, HSTS, cookies com `Secure`, API navegável do DRF desligada e recusa de subir com a `SECRET_KEY` de exemplo
- [x] Webhook da Abacate Pay só funciona com segredo configurado, comparado em tempo constante. Sem o segredo, qualquer um poderia marcar uma cobrança como paga
- [x] Logs da aplicação aparecem na saída do servidor (antes se perdiam)
- [x] Testes automatizados: 191 casos — produtos 16 (margem, preço sugerido, foto), financeiro 28 (leitura de OFX, importação ponta a ponta, extrato que repete o que já foi lançado e os insights), contas 14 (recuperação de senha e entrega pelo Resend), marketing 58 (margem real no prompt, isolamento por negócio, recomendações e a geração de imagem), pagamentos 38 (webhook só com o segredo certo, PIX pago vira uma receita e uma só, estorno, valor zero ou negativo recusado, falhas da Abacate Pay e isolamento por negócio), vendas 37 (lucro real, estoque que nunca fica negativo, cancelamento, PIX de produto, resumo do mês, insights, assistente e recomendações)
- [x] Teste das telas num navegador automático (desktop e celular, admin e membro): cadastro, produtos, vendas, movimentações, extrato, PIX, assistente, marketing e recuperação de senha
- [ ] Testes com a IA de verdade: os testes simulam as respostas da DeepSeek, da Anthropic e da Cloudflare; nenhum chama o modelo real

---

## O que ainda falta (do escopo do TCC)

Com base no `Escopo TCC.pdf`, os itens abaixo ainda não foram implementados:

Nada. Os dois itens do escopo foram implementados — recomendações de marketing e geração de imagens.

Fora do escopo do PDF, mas pendente: as **variáveis do Resend no Render** e um **domínio verificado** para o e-mail chegar a qualquer usuário (o código está pronto e testado), os leitores de extrato em **CSV** e **PDF**, a **conexão direta com o banco** (hoje a tela é um protótipo) e o **giro de estoque**.

---

## Como testar cada feature manualmente

| Feature | Como testar |
|---|---|
| Página inicial | Abrir `/` deslogado → tocar no botão da demo de PIX (o status vira "pago") → usar a calculadora de margem → abrir o FAQ |
| Cadastro/login | Acessar a landing page → "Entrar" → criar conta ou usar Google |
| Recuperação de senha | Tela de login → "Esqueci minha senha" → informar o e-mail → abrir o link recebido → definir a senha nova → entrar com ela |
| Onboarding | Após o primeiro login, preencher nome do negócio |
| Produtos | Menu "Produtos" → cadastrar/editar/remover |
| Vendas | Menu "Vendas" → "Registrar venda" → escolher o produto e a quantidade → conferir o lucro real na prévia → registrar. O estoque do produto baixa e a entrada aparece em Movimentações com origem "Venda". Pedir mais que o estoque deve mostrar "Só há N em estoque". Cancelar a venda devolve o estoque |
| Financeiro | Login como admin → aba "Financeiro" → lançar transação |
| PIX | Login como admin → aba "Financeiro" → "Cobrança PIX" → preencher e gerar |
| Marketing IA | Menu "Marketing" → escrever o pedido (ou escolher uma sugestão) → a IA responde no chat |
| Imagem da campanha | Com `CLOUDFLARE_ACCOUNT_ID`/`CLOUDFLARE_API_TOKEN` (ou `MARKETING_IMAGE_FALLBACK=True`), pedir uma campanha ou post: a imagem aparece dentro da resposta, com botão para baixar. Sem provedor, a campanha sai só com o texto |
| Importar extrato | Login como admin → "Movimentações" → "Importar extrato" → anexar um `.ofx` → conferir a lista → "Importar". Reenviar o mesmo arquivo deve trazer tudo desmarcado como "Já importado". Registrar uma venda e importar um extrato com o mesmo valor no mesmo dia deve trazer a linha desmarcada como "Já lançado: Venda" |
| Assistente financeiro | Login como admin → abrir o chat → perguntar sobre os números; recarregar a página e conferir que a conversa continua lá |
| Admin/banco de dados | Acessar `/admin/` logado como superusuário Django |
