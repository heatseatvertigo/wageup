# WageUp — Documento do Projeto

> **Documento-base do Trabalho de Conclusão de Curso (TCC).**
> Descreve o que é o WageUp, o problema que ele enfrenta (com base em pesquisas sobre o microempreendedor brasileiro), a proposta, o escopo da prova de conceito e o que ficou para versões futuras.
>
> Estado da prova de conceito: setembro de 2026 · Produção: <https://wageup.onrender.com>
> Detalhes técnicos de implementação estão em [`DOCUMENTACAO-TCC.md`](DOCUMENTACAO-TCC.md). Este documento fica no **o quê** e no **porquê**.

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Contexto: o microempreendedor brasileiro](#2-contexto-o-microempreendedor-brasileiro)
3. [As dores do MEI](#3-as-dores-do-mei)
4. [Mudanças regulatórias (2026–2027)](#4-mudanças-regulatórias-20262027)
5. [Síntese: o que falta no operacional](#5-síntese-o-que-falta-no-operacional)
6. [Problema de pesquisa](#6-problema-de-pesquisa)
7. [Objetivos](#7-objetivos)
8. [Público-alvo e implicações de design](#8-público-alvo-e-implicações-de-design)
9. [Proposta de valor e diferencial](#9-proposta-de-valor-e-diferencial)
10. [Como o WageUp responde às dores](#10-como-o-wageup-responde-às-dores)
11. [Estrutura do sistema](#11-estrutura-do-sistema)
12. [Princípio de integração: do número à ação](#12-princípio-de-integração-do-número-à-ação)
13. [Fluxo principal do usuário](#13-fluxo-principal-do-usuário)
14. [Lucro real: o cálculo de margem](#14-lucro-real-o-cálculo-de-margem)
15. [Recebimentos](#15-recebimentos)
16. [Inteligência Artificial](#16-inteligência-artificial)
17. [Tom e linguagem](#17-tom-e-linguagem)
18. [Tecnologia (o essencial)](#18-tecnologia-o-essencial)
19. [Modelo de dados conceitual](#19-modelo-de-dados-conceitual)
20. [Requisitos](#20-requisitos)
21. [Segurança e privacidade](#21-segurança-e-privacidade)
22. [Escopo da prova de conceito](#22-escopo-da-prova-de-conceito)
23. [Limitação da integração de pagamentos e arquitetura futura](#23-limitação-da-integração-de-pagamentos-e-arquitetura-futura)
24. [Critérios de sucesso](#24-critérios-de-sucesso)
25. [Roadmap](#25-roadmap)
26. [Resumo do projeto](#26-resumo-do-projeto)
27. [Referências](#27-referências)

---

## 1. Visão geral

O **WageUp** é uma plataforma web responsiva que ajuda **microempreendedores brasileiros** a controlar o dinheiro do negócio e a decidir o que fazer para crescer.

O ponto de partida é um problema comum: o dinheiro entra por vários caminhos (Pix, dinheiro, cartão), mas o empreendedor raramente sabe **quanto vendeu, quanto disso é lucro, quais produtos rendem mais e o que fazer a partir desses números**.

O WageUp transforma dados financeiros em **informação compreensível, recomendação e ação prática**:

> **Dados financeiros → Análise → Insight → Recomendação → Ação**

O sistema não se limita a registrar movimentações: usa o que foi registrado para apoiar decisões.

### Conceito central

> **Transformar recebimentos em crescimento.**
> Receba. Entenda. Decida. Cresça.

---

## 2. Contexto: o microempreendedor brasileiro

### 2.1 Tamanho do público

- O MEI é a principal porta de entrada no empreendedorismo. Entre janeiro e setembro de 2025 foram abertos **3,87 milhões de pequenos negócios, e 77,1% deles eram MEIs** [1].
- A base ativa chegava a **quase 15 milhões de registros** em 2025 [2].
- **Serviços** lidera com folga, seguido do **comércio** [3]: negócios enxutos, com atendimento direto ao consumidor e pouca estrutura.

Trata-se, portanto, de um público de dezenas de milhões de pessoas (considerando as famílias que dependem desses negócios), com necessidades de gestão muito parecidas entre si.

### 2.2 Perfil do MEI

| Dimensão | O que as pesquisas mostram | Por que importa para o WageUp |
|---|---|---|
| **Dependência de renda** | 93,8% consideram o negócio sua principal ou única fonte de renda; cerca de 76% dizem que é a **única** [4][5]. Em dois terços dos casos, outras pessoas da família também contribuem com a renda da casa [5]. | O negócio é o sustento da família. Um erro de gestão afeta a casa inteira. |
| **Renda** | Uma fonte aponta renda familiar média de cerca de **R$ 6.715**, com 44,9% declarando até dois salários mínimos [6]; o *Atlas dos Pequenos Negócios* indica **R$ 5.542** em 2024 [5]. | Margem para erro é pequena. A ferramenta precisa ser gratuita ou muito barata. |
| **Escolaridade** | **Dois em cada três** MEIs têm até o ensino médio completo [5]. | Linguagem simples, sem jargão contábil. |
| **Motivação** | **56%** empreenderam por falta de outra opção de renda; **três em cada quatro** passaram cinco anos ou mais na informalidade antes de se formalizar [5]. | Empreendedor por necessidade, sem formação em gestão. |
| **Local de trabalho** | **54%** operam em casa ou no endereço do cliente; só **27%** têm estabelecimento comercial [5]. | Casa e negócio se misturam — e o dinheiro também. |

> **Nota sobre a renda.** Os dois valores vêm de levantamentos diferentes, com amostras, anos de referência e forma de coleta próprios (pesquisa de perfil por questionário × consolidação estatística do *Atlas*). Por isso não são comparáveis diretamente. O mais seguro é citar os dois, com a fonte e o ano de cada um, e tratar a faixa entre eles como ordem de grandeza.

---

## 3. As dores do MEI

### 3.1 Mistura de finanças pessoais e do negócio — a dor nº 1

- **61%** dos empreendedores usaram a conta pessoal para pagar despesas da empresa em 2025. Em 2023 eram **60%**: praticamente não mudou, mesmo com mais acesso a contas PJ [7][8].
- A mistura vai além: inclui usar o caixa do negócio para contas particulares, fazer retiradas sem registro e receber vendas direto na conta PF. O resultado é que **fica difícil saber quanto a empresa fatura de fato, quais são os custos, qual é a margem e quanto dá para investir** [7].

### 3.2 Controle financeiro precário

- **30%** usam planilhas, **25%** ainda dependem de caderno, só **20%** usam aplicativos ou sistemas e **10%** não fazem controle nenhum [9].
- **Metade** dos pequenos empreendedores tem controle financeiro considerado precário [10].
- Há diferença regional: **Sudeste e Sul** lideram no uso de planilhas; **Norte e Nordeste** se destacam pelo caderno [11].
- Dado mais antigo do Sebrae Minas (usar com ressalva de data): **23%** dos MEIs não calculam o valor dos produtos, **30%** nunca controlaram contas a pagar e **15%** controlam as finanças "de cabeça" [12].

### 3.3 Obrigações fiscais esquecidas ou atrasadas

- Em abril de 2024, **41,2%** dos MEIs estavam inadimplentes com a Receita Federal, cerca de **6,5 milhões** de pessoas [13].
- A inadimplência suspende benefícios previdenciários (aposentadoria, auxílio-doença, salário-maternidade), e **12 meses de atraso** podem levar à exclusão do regime e ao cancelamento do CNPJ [2].
- Faltando 20 dias para o prazo da declaração anual, a Receita tinha recebido só **38%** das DASN-Simei esperadas, com mais de **10 milhões** de MEIs pendentes [14].
- O atraso tem custo concreto: multa de **0,33% ao dia** desde o primeiro dia [15].

### 3.4 Nota fiscal

- Desde setembro de 2023 o MEI prestador de serviço é obrigado a usar o **emissor nacional de NFS-e**. No lançamento houve instabilidade, e prestadores relataram atraso no recebimento por não conseguirem emitir nota [16][17].
- Há atrito até em cidades grandes: São Paulo usava lista própria de códigos de serviço em vez do padrão da LC 116, o que dificulta achar o código certo da atividade [18].

### 3.5 Crédito

- **67%** dos MEIs que tentaram crédito tiveram o pedido negado; só **12%** conseguiram o valor total [19].
- Para **42%**, a **burocracia** é o principal entrave, acima até dos juros [19].
- Entre as causas de negativa estão **ausência de comprovantes, documentos desatualizados e inconsistências cadastrais** [20] — problemas que um controle financeiro organizado resolve diretamente.

### 3.6 Digitalização

- **74%** dos MEIs usam internet, contra 88,1% das microempresas e 95,7% das pequenas empresas [21].
- **Menos de 13%** usam a internet para cursos, marketplaces ou plataformas de gestão [21].
- Ao mesmo tempo, **vendem pelo celular**: WhatsApp, Instagram e Facebook são os canais digitais mais usados para vender [22][23].

Existe um divisor claro entre **ter presença digital** (vender no Instagram) e **ter uma operação digitalizada** (controlar o negócio num sistema).

### 3.7 Sobrevivência

- Os MEIs têm a **maior taxa de mortalidade** entre os pequenos negócios: **29% fecham em até 5 anos** [24].
- Entre os que fecharam havia mais gente que empreendeu por necessidade, com menos conhecimento do negócio, menos acesso a crédito e menos capacitação [25].
- Quem empreende por **oportunidade** sobrevive em **58%** dos casos; por **necessidade**, só **28%** [26].

---

## 4. Mudanças regulatórias (2026–2027)

- **O teto continua o mesmo:** faturamento anual de **R$ 81 mil**, com tolerância de 20% (**R$ 97.200**) antes do desenquadramento obrigatório. Os projetos para aumentar o limite ainda não viraram lei [27].
- **A reforma tributária criou o nanoempreendedor:** pessoa física que fatura menos de **R$ 40.500 por ano**, sem MEI, e não é contribuinte de IBS/CBS [28].
- **Vem mais fiscalização.** Um dos impactos previstos é o cálculo do faturamento **considerando valores recebidos no CPF**. Exemplo: quem fatura R$ 70 mil no CNPJ e mais R$ 30 mil como autônomo no CPF soma R$ 100 mil, estoura o limite e é desenquadrado, com impostos retroativos [29][30].

**Consequência:** a mistura entre pessoa física e jurídica deixa de ser só um problema de organização e passa a ser um **risco fiscal real**. Esse é um argumento forte para uma ferramenta que organize os recebimentos do negócio.

---

## 5. Síntese: o que falta no operacional

Cruzando os dados das seções 2 a 4, estas são as lacunas que o projeto identifica. **É uma interpretação dos autores**, não um resultado direto das pesquisas:

1. **Separação PF/PJ sem atrito.** O MEI não separa porque dá trabalho e porque recebe no Pix pessoal. Falta uma forma de classificar cada entrada e saída (negócio ou pessoal) sem exigir duas contas.
2. **Saber o lucro real, não só o faturamento.** Ele confunde dinheiro que entrou com dinheiro que sobrou e não tem noção de custo nem de margem.
3. **Pró-labore definido.** Sem um "salário" para si mesmo, retira dinheiro aleatoriamente e descapitaliza o negócio.
4. **Agenda fiscal automática.** DAS todo dia 20, DASN-Simei até 31/05, alerta de proximidade do teto de R$ 81 mil (somando o CPF).
5. **Previsão de caixa.** Saber se vai ter dinheiro no mês que vem, principalmente quem vende a prazo.
6. **Histórico organizado para conseguir crédito.** Comprovação de faturamento é justamente o que falta na hora de pedir empréstimo.
7. **Tudo no celular e em linguagem simples.** O público é mobile, tem escolaridade majoritariamente até o ensino médio e já vive no WhatsApp.

A seção [10](#10-como-o-wageup-responde-às-dores) mostra quais dessas lacunas a prova de conceito já cobre e quais ficam para o roadmap.

---

## 6. Problema de pesquisa

Microempreendedores administram vendas, custos, recebimentos e divulgação ao mesmo tempo em que executam o próprio trabalho. Ferramentas de gestão tradicionais são complexas demais para esse público, e controles manuais (caderno, planilha, "de cabeça") não consolidam a informação.

Problemas considerados pelo projeto:

- dificuldade de acompanhar diferentes formas de recebimento;
- falta de visão consolidada do faturamento;
- dificuldade para estimar lucro e margem;
- dificuldade para identificar os produtos mais rentáveis;
- dificuldade para transformar dados financeiros em decisões;
- necessidade de criar ações de marketing sem conhecimento especializado;
- falta de integração entre controle financeiro e ações para vender mais.

**Pergunta norteadora:**

> *Como uma plataforma digital simples, com apoio de inteligência artificial, pode ajudar o microempreendedor a entender o resultado real do seu negócio e transformar esse entendimento em ações práticas de crescimento?*

O WageUp procura reduzir a distância entre **registrar o que aconteceu** e **entender o que fazer a partir disso**.

---

## 7. Objetivos

### 7.1 Objetivo geral

Desenvolver uma plataforma web que permita ao microempreendedor consolidar seus recebimentos, conhecer o lucro real do negócio e receber recomendações de ação baseadas nos próprios dados, com apoio de inteligência artificial.

### 7.2 Objetivos específicos

1. Permitir o cadastro do negócio e dos produtos com preço, custo e taxas.
2. Calcular a margem real de cada produto, considerando custos extras, taxas de cartão/Pix e impostos.
3. Consolidar recebimentos manuais, cobranças Pix e extratos bancários numa visão única.
4. Gerar cobranças Pix com confirmação automática do pagamento no financeiro.
5. Apresentar indicadores financeiros em linguagem simples.
6. Oferecer um assistente que responda perguntas sobre os números do negócio.
7. Gerar recomendações e conteúdos de marketing a partir da margem real dos produtos.
8. Validar tecnicamente o fluxo **dados → insight → recomendação → ação**.

---

## 8. Público-alvo e implicações de design

**Público principal:** microempreendedores e pequenos negócios com operação enxuta, sem conhecimento aprofundado de contabilidade, administração ou análise de dados.

Perfis considerados:

- vendedores ambulantes e de alimentos (marmita, doces, lanches);
- pequenos comerciantes e revendedores;
- prestadores de serviço (beleza, manutenção, aulas);
- profissionais autônomos;
- microempreendedores individuais (MEIs);
- pequenos negócios que recebem por Pix, dinheiro e cartão.

### Como a pesquisa orientou o design

| Evidência | Decisão de produto |
|---|---|
| 2 em cada 3 MEIs têm até o ensino médio [5] | Linguagem do dia a dia; o assistente é proibido de usar jargão ("fluxo de caixa", "capital de giro", "ticket médio") |
| Vendem por WhatsApp e Instagram [22] | Marketing gera textos prontos para esses canais |
| O público é mobile | Interface responsiva, pensada primeiro para o celular |
| Menos de 13% usam plataformas de gestão [21] | Cadastro mínimo, onboarding curto, valor mostrado antes do cadastro (calculadora de margem e demonstração de Pix abertas na página inicial) |
| 25% usam caderno e 10% não controlam nada [9] | Importação de extrato e Pix conciliado automaticamente, para reduzir a digitação |
| 23% não calculam o preço dos produtos [12] | Calculadora de margem real e de preço sugerido para uma margem desejada |

---

## 9. Proposta de valor e diferencial

O WageUp propõe que o empreendedor consiga:

1. **Registrar ou consolidar** seus recebimentos;
2. **Visualizar** o desempenho do negócio;
3. **Entender** os principais indicadores;
4. **Receber** interpretações e recomendações;
5. **Transformar** recomendações em ações de produto e marketing.

A plataforma funciona como um **copiloto de crescimento do negócio**.

### Diferencial: Entender → Decidir → Agir

| Etapa | O que acontece |
|---|---|
| **1. Entender** | Consolidar e analisar os dados financeiros, com o lucro real (não só o faturamento) |
| **2. Decidir** | Interpretar os resultados e sugerir ações |
| **3. Agir** | Transformar a recomendação numa ação de produto ou marketing |

Aplicativos de controle financeiro param no "entender"; ferramentas de marketing começam no "agir" sem olhar para os números. O WageUp liga as duas pontas, sem deixar de ter o **financeiro como núcleo**.

---

## 10. Como o WageUp responde às dores

Legenda: ✅ implementado na prova de conceito · 🟡 parcial · 🔜 planejado

| Dor / lacuna | Evidência | Resposta do WageUp | Status |
|---|---|---|---|
| Não saber o lucro real | 23% não calculam o preço [12]; mistura PF/PJ esconde a margem [7] | Margem real por produto (custo + embalagem/frete + taxa + imposto) e preço sugerido para uma margem-alvo | ✅ |
| Controle precário (caderno, planilha, nada) | 30% planilha, 25% caderno, 10% nada [9] | Lançamentos de entrada e saída, calendário, gráfico do semestre, totais por período | ✅ |
| Recebimentos espalhados | Vendas caem na conta PF [7] | Cobrança Pix que vira entrada automaticamente; importação de extrato bancário (OFX) | ✅ |
| Dificuldade de interpretar números | Escolaridade [5]; controle "de cabeça" [12] | Assistente financeiro em linguagem simples; insights automáticos no painel | ✅ |
| Marketing sem conhecimento especializado | Vendem por WhatsApp/Instagram [22] | Campanhas com IA e recomendações do que divulgar, baseadas na margem | ✅ |
| Histórico para pedir crédito | Negativas por falta de comprovantes [20] | Histórico organizado de lançamentos e cobranças; relatório para crédito ainda não existe | 🟡 |
| Previsão de caixa | Quem vende a prazo não sabe se terá dinheiro | Painel mostra o valor "a receber" das cobranças Pix pendentes; projeção do mês seguinte não existe | 🟡 |
| Tudo no celular, linguagem simples | Perfil mobile [22] | Interface responsiva e tom próximo | ✅ |
| Separação PF/PJ sem atrito | 61% misturam contas [7] | Classificar cada lançamento como "negócio" ou "pessoal" | 🔜 |
| Pró-labore | Retiradas sem registro [7] | Definir e acompanhar um "salário" do dono | 🔜 |
| Agenda fiscal | 41,2% inadimplentes [13]; 38% das DASN entregues perto do prazo [14] | Lembretes do DAS (dia 20) e da DASN-Simei (31/05) | 🔜 |
| Alerta do teto de R$ 81 mil | Fiscalização somando CPF [29] | Acompanhar o faturamento acumulado do ano e avisar ao se aproximar do limite | 🔜 |
| Nota fiscal | Instabilidade do emissor nacional [17] | Fora do escopo; o assistente orienta a procurar um contador | — |

A prova de conceito concentra-se nas dores de **lucro real, consolidação dos recebimentos, interpretação dos números e ação de marketing**. As dores fiscais e de separação PF/PJ são o próximo passo natural (seção [25](#25-roadmap)).

---

## 11. Estrutura do sistema

O WageUp é organizado em três frentes:

### 11.1 Financeiro — a base

Reúne e apresenta:

- recebimentos e despesas (lançamentos manuais, cobranças Pix e extrato importado);
- faturamento, despesas e lucro do período;
- valores já recebidos e a receber via Pix;
- evolução mês a mês (gráfico do semestre) e dia a dia (calendário);
- origem de cada lançamento (manual, Pix ou extrato).

### 11.2 Assistente Financeiro — a camada de inteligência

O usuário faz perguntas sobre o próprio negócio e recebe respostas baseadas nos seus dados. Exemplos de perguntas que o assistente responde hoje:

- "Quanto eu faturei este mês?"
- "Quanto eu lucrei?"
- "Minhas vendas estão melhores que no mês passado?"
- "Quanto tenho para receber no Pix?"
- "Qual produto me dá mais lucro por unidade?"
- "O que posso fazer para melhorar meu resultado?"

As conversas ficam salvas e podem ser retomadas. Perguntas sobre **vendas por produto** ("qual produto vendeu mais?") ainda não têm resposta, porque a prova de conceito não registra vendas por item (ver [Limitações](#224-limitações-conhecidas)).

### 11.3 Produto e Marketing — a camada de ação

A partir do catálogo e da margem real de cada produto:

- recomenda **o que divulgar agora** (e o que **não** divulgar — produto em prejuízo precisa de revisão de preço, não de propaganda);
- gera campanhas com **chamada principal, ideia de imagem, legenda e chamada para ação**, prontas para Instagram, WhatsApp ou TikTok;
- guarda o histórico das campanhas por produto.

---

## 12. Princípio de integração: do número à ação

O conceito central do WageUp é conectar **informação financeira** com **ação de crescimento**:

> **Financeiro → Insight → Recomendação → Marketing**

**Como funciona na prova de conceito** (exemplo ilustrativo):

1. O produto "Kit festa" custa R$ 79,00, com R$ 38,00 de custo, R$ 2,00 de embalagem, 4% de taxa e 6% de imposto. A margem real é de R$ 31,10 (39% do preço), e ele nunca foi divulgado.
2. O painel de recomendações sugere: *"Estreie a divulgação — Kit festa nunca teve campanha e é o que mais rende: R$ 31,10 por unidade (39% do preço)."*
3. O botão **"Usar no formulário"** preenche o gerador de campanha com o produto, o canal e o objetivo.
4. O usuário revisa e clica em **Gerar**. A IA escreve a campanha já sabendo a margem real — e é instruída a **nunca sugerir um desconto maior que ela**.

O inverso também acontece: um produto que dá prejuízo recebe a recomendação *"Revise o preço"*, e não uma campanha para vender mais no vermelho.

**A decisão final é sempre do usuário:** a IA sugere, a pessoa confirma.

---

## 13. Fluxo principal do usuário

```text
                    ┌─────────────────────┐
                    │     ONBOARDING      │
                    │ Negócio + Produtos  │
                    │ + Custos e taxas    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  DADOS FINANCEIROS  │
                    │ Pix (automático)    │
                    │ Lançamento manual   │
                    │ Extrato bancário    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      DASHBOARD      │
                    │ Entradas / Saídas / │
                    │ Lucro / A receber   │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
          ┌─────────────────┐   ┌────────────────────┐
          │ ASSISTENTE      │   │ PRODUTO E          │
          │ FINANCEIRO      │──▶│ MARKETING          │
          │                 │   │                    │
          │ Perguntas       │   │ Recomendações      │
          │ Insights        │   │ Campanhas          │
          │ Sugestões       │   │ Conteúdo           │
          └─────────────────┘   └────────────────────┘
```

---

## 14. Lucro real: o cálculo de margem

É a regra de negócio mais importante do WageUp, porque ataca diretamente a confusão entre **dinheiro que entrou** e **dinheiro que sobrou**.

A conta que o microempreendedor costuma fazer é **preço − custo**. Ela ignora embalagem, frete, a taxa da maquininha ou do Pix e o imposto, que saem do mesmo bolso. O produto parece lucrativo e, na prática, pode dar prejuízo.

| Conceito | Como é calculado |
|---|---|
| Custo por unidade | custo do produto + outros custos (embalagem, frete, etiqueta) |
| Taxas | preço × (% da taxa de cartão/Pix + % de imposto) |
| **Margem real (R$)** | preço − custo por unidade − taxas |
| **Margem (%)** | margem real ÷ preço — "quanto do preço sobra" |
| Markup (%) | (preço − custo) ÷ custo — "quanto foi acrescentado sobre o custo" |
| **Preço sugerido** | custo ÷ (1 − % taxas − % margem desejada) |

**Exemplo:** um bolo vendido a R$ 20,00, com custo de R$ 8,00, embalagem de R$ 1,50, taxa de cartão de 4% e imposto de 6%.

| | Conta ingênua | Conta do WageUp |
|---|---|---|
| Sobra por bolo | R$ 12,00 (60%) | **R$ 8,50 (42,5%)** |

Para ter 50% de margem, o bolo precisaria custar **R$ 23,75**. Quando taxas e margem desejada somam 100% ou mais, o sistema avisa que **nenhum preço fecha a conta**, em vez de mostrar um número absurdo. Margem negativa aparece como **"Prejuízo"**, com texto — nunca apenas com cor.

Essa mesma margem real é a que alimenta o assistente, os insights e as recomendações de marketing.

---

## 15. Recebimentos

### 15.1 Pix — fluxo automatizado ✅

Na prova de conceito, o WageUp usa a **Abacate Pay** para criar cobranças e confirmar pagamentos automaticamente.

1. O usuário cria a cobrança (valor, descrição e, opcionalmente, dados do cliente).
2. O WageUp pede a cobrança à Abacate Pay.
3. A Abacate Pay devolve o **QR Code** e o código **"copia e cola"**, válidos por 1 hora.
4. O cliente paga.
5. O WageUp fica sabendo do pagamento por **dois caminhos**: o aviso da Abacate Pay (*webhook*) e uma consulta que a própria tela faz a cada 3 segundos.
6. O pagamento vira automaticamente uma **entrada no financeiro**, sem digitação.
7. O painel é atualizado. Estornos geram a saída correspondente.

```text
Cliente
   │ paga o Pix
   ▼
Abacate Pay
   │ webhook  +  consulta periódica
   ▼
Backend WageUp
   │ registra a entrada (sem duplicar)
   ▼
Banco de dados
   │
   ▼
Dashboard / Assistente
```

O sistema garante que um mesmo pagamento **nunca vire dois lançamentos**, mesmo que o aviso chegue repetido.

### 15.2 Dinheiro e cartão — registro manual 🟡

Recebimentos em dinheiro ou cartão são registrados como **lançamentos de entrada**, com valor, data e descrição. Exemplo: *"no fim do dia, entrou R$ 180 em dinheiro"*.

Na prova de conceito **não existe um campo específico de forma de pagamento**: o meio fica na descrição, e o painel não separa os totais por Pix, dinheiro e cartão. Os lançamentos são identificados pela origem (manual, Pix ou extrato).

### 15.3 Extrato bancário ✅

Previsto inicialmente como evolução, foi **implementado**:

- o usuário envia o extrato no formato **OFX**, que os principais bancos exportam;
- o sistema lê os lançamentos e mostra uma **tela de conferência**: o usuário desmarca o que não é do negócio (como transferências entre contas próprias) e corrige descrições antes de confirmar;
- **reimportar o mesmo extrato não duplica nada**;
- o **arquivo nunca é guardado** — só os lançamentos confirmados.

Esse passo de conferência já é um primeiro instrumento de **separação PF/PJ**: o que é pessoal simplesmente não entra.

Formatos CSV e PDF e a conexão direta com o banco (Open Finance) ficam para o futuro. Na plataforma existe apenas uma tela ilustrativa, marcada como "em breve", explicando como essa conexão funcionaria.

---

## 16. Inteligência Artificial

A IA é usada como **camada de interpretação e geração**, e não como um chatbot isolado: ela sempre recebe o contexto do negócio do usuário.

### 16.1 Onde é usada

| Área | O que a IA faz |
|---|---|
| **Painel** | Gera de 3 a 4 insights sobre a saúde financeira, os recebíveis, o estoque e o produto de melhor margem |
| **Assistente financeiro** | Responde perguntas sobre os números do negócio, em linguagem simples |
| **Recomendações de marketing** | Indica o que divulgar, em qual canal e com qual objetivo |
| **Campanhas** | Escreve chamada, ideia de imagem, legenda e chamada para ação |

### 16.2 Princípio: o sistema calcula, a IA interpreta

Modelos de linguagem erram contas sem avisar, e num aplicativo financeiro um valor errado é um problema que o usuário não percebe. Por isso, **todos os números são calculados pelo sistema antes** de chegar à IA, e ela é instruída a:

- usar **apenas** os números recebidos;
- **não refazer** contas;
- dizer com franqueza quando não tem a informação, e explicar o que o usuário pode registrar para passar a ter;
- não se passar por contador: para imposto, nota fiscal ou declaração, orientar a procurar um profissional.

Esse cuidado reduz o risco de **alucinação** — quando a IA inventa uma informação com aparência de verdadeira.

### 16.3 Cuidados adicionais

- **A IA nunca recebe dados pessoais dos clientes** do empreendedor (CPF, e-mail, telefone): só o necessário para a análise.
- **Os números vêm do banco de dados, não da tela**, para que ninguém consiga manipular o que a IA recebe.
- **O histórico da conversa é guardado pelo servidor**, e não pelo navegador, para que não seja possível forjar falas anteriores do assistente.
- **Se a IA estiver indisponível**, o sistema usa regras próprias e continua respondendo, sem quebrar.
- **Limite de uso** por usuário, porque cada chamada à IA tem custo.

### 16.4 Modelos utilizados

- **Claude Haiku 4.5** (Anthropic): campanhas, recomendações e insights.
- **DeepSeek** (`deepseek-chat`): assistente financeiro, com o Claude como alternativa.

A geração de **imagens** com IA está prevista, mas não implementada: hoje a IA apenas **descreve** a imagem sugerida para a campanha.

---

## 17. Tom e linguagem

O perfil de escolaridade do público [5] torna a linguagem um requisito, e não um detalhe.

Atributos da comunicação:

- **Simples** — sem linguagem financeira técnica;
- **Próxima** — como uma parceira do negócio ("um amigo que entende de dinheiro, não um banco");
- **Acionável** — cada informação aponta um próximo passo;
- **Motivadora** — destaca oportunidades;
- **Inteligente** — responde com base nos dados do próprio negócio.

| Em vez de | Preferir |
|---|---|
| "Sua margem operacional apresentou redução." | "Seu lucro diminuiu esta semana." |
| "Ticket médio abaixo do esperado." | "Cada venda está deixando menos dinheiro no bolso." |
| "As vendas caíram." | "As vendas caíram. Que tal criar uma promoção para amanhã?" |
| "Margem de contribuição negativa." | "Esse produto está dando prejuízo: você perde R$ 2,00 a cada venda." |

Na prática, o assistente é instruído a **começar pela resposta**, usar **três ou quatro frases**, evitar termos como "fluxo de caixa" e "capital de giro" e **terminar com um próximo passo concreto**.

---

## 18. Tecnologia (o essencial)

| Camada | Tecnologia | Por quê |
|---|---|---|
| Interface | HTML, CSS e JavaScript, sem framework | Leve, sem etapa de compilação, funciona bem em celulares mais simples |
| Servidor | Python 3.12 com **Django 6** e **Django REST Framework** | Framework maduro, com autenticação, banco de dados e painel administrativo prontos |
| Banco de dados | **PostgreSQL** (Neon) | Confiável, gratuito no plano inicial, com backup automático |
| Pagamentos | **Abacate Pay** (Pix) | API simples de Pix para validar o fluxo de cobrança |
| Inteligência artificial | **Claude Haiku 4.5** e **DeepSeek** | Modelos rápidos e de baixo custo por chamada |
| E-mail | **Resend** | Envio do link de recuperação de senha |
| Login social | **Google** | Entrar sem criar senha |
| Hospedagem | **Render** | Deploy automático a partir do GitHub, plano gratuito |

**Arquitetura em camadas:**

```text
 Navegador (celular ou computador)
          │  HTTPS
          ▼
 ┌─────────────────────────────┐
 │  WageUp (Django)            │
 │  • Interface (página única) │
 │  • API REST                 │──► Abacate Pay (Pix)
 │  • Regras de negócio        │◄── Webhook de pagamento
 │  • Cálculo de indicadores   │──► Claude / DeepSeek (IA)
 └──────────────┬──────────────┘──► Resend (e-mail) · Google (login)
                ▼
         PostgreSQL (Neon)
```

O custo de infraestrutura da prova de conceito é **zero** (planos gratuitos). Os únicos custos variáveis são as chamadas às APIs de IA.

---

## 19. Modelo de dados conceitual

| Entidade | Representa | Principais dados | Status |
|---|---|---|---|
| **Usuário** | Pessoa que usa a plataforma | nome, e-mail, senha (criptografada), perfil de acesso | ✅ |
| **Negócio** | O empreendimento do usuário | nome do negócio | ✅ |
| **Produto** | Produto ou serviço vendido | nome, categoria, unidade, preço, custo, outros custos, % taxa, % imposto, estoque, estoque mínimo, foto, ativo/inativo | ✅ |
| **Transação** | Entrada ou saída de dinheiro | valor, data, tipo (entrada/saída), descrição, origem (manual, Pix, extrato), referência externa | ✅ |
| **Cobrança** | Cobrança Pix | valor, status (pendente, paga, expirada, reembolsada…), cliente, QR Code | ✅ |
| **Importação de extrato** | Registro de um extrato importado | nome do arquivo, quantidade importada e ignorada (o arquivo em si não é guardado) | ✅ |
| **Campanha** | Campanha de marketing gerada | produto, canal, objetivo, texto gerado | ✅ |
| **Conversa** | Conversa com o assistente | título, mensagens | ✅ |
| **Meta** | Objetivo financeiro do período | período, valor objetivo | 🔜 |

```text
Usuário ─── Negócio ─┬── Produtos ── Campanhas
                     ├── Transações ── (Importações de extrato)
                     ├── Cobranças Pix ──► geram Transações
                     └── Conversas ── Mensagens
```

Cada usuário só enxerga os dados do **próprio negócio**.

---

## 20. Requisitos

### 20.1 Requisitos funcionais

| Código | Requisito | Status | Observação |
|---|---|---|---|
| RF01 | Cadastro e acesso do usuário | ✅ | E-mail e senha, login com Google, recuperação de senha por e-mail |
| RF02 | Cadastro do negócio | ✅ | Nome do negócio no onboarding |
| RF03 | Cadastro de produtos com preço e custo | ✅ | Inclui outros custos, taxas, imposto, estoque e foto |
| RF04 | Registro manual de recebimentos | 🟡 | Entradas e saídas manuais; sem campo próprio de forma de pagamento |
| RF05 | Geração de cobrança Pix | ✅ | QR Code e copia e cola via Abacate Pay |
| RF06 | Registro automático de pagamento | ✅ | Webhook + consulta periódica; vira entrada no financeiro |
| RF07 | Dashboard com indicadores consolidados | ✅ | Entradas, saídas, lucro, recebido e a receber, calendário, gráfico do semestre |
| RF08 | Cálculo de faturamento, lucro e margem | ✅ | Margem real por produto; lucro do período |
| RF09 | Assistente financeiro em linguagem natural | ✅ | Com histórico de conversas |
| RF10 | Recomendações baseadas nos dados | ✅ | Insights do painel e recomendações de marketing |
| RF11 | IA para ações de produto e marketing | 🟡 | Textos de campanha implementados; imagens não |
| RF12 | Integração entre financeiro e marketing | 🟡 | Recomendações preenchem o gerador de campanha com um clique; o assistente sugere ações, mas não abre a campanha diretamente |
| RF13 | Importação de extrato bancário | ✅ | OFX, com conferência e sem duplicar (não previsto no escopo inicial) |
| RF14 | Metas financeiras | 🔜 | Não implementado |

### 20.2 Requisitos não funcionais

| Código | Requisito | Como foi atendido |
|---|---|---|
| RNF01 | Responsividade | Interface pensada primeiro para o celular |
| RNF02 | Usabilidade | Linguagem simples, cálculos respondendo enquanto o usuário digita, cor nunca como único indicador |
| RNF03 | Desempenho | Interface leve, sem framework; respostas da IA limitadas em tamanho |
| RNF04 | Segurança | Ver seção [21](#21-segurança-e-privacidade) |
| RNF05 | Integração | Comunicação por API com Abacate Pay, Anthropic, DeepSeek, Resend e Google |
| RNF06 | Manutenibilidade | Sistema dividido em módulos independentes; leitor de extrato preparado para novos formatos; 68 testes automatizados |
| RNF07 | Resiliência | Toda integração externa tem alternativa: sem IA, o sistema usa regras próprias; sem webhook, consulta o provedor |

---

## 21. Segurança e privacidade

Como o sistema lida com informações financeiras, a segurança foi considerada desde a arquitetura:

- **Autenticação** por token, com senhas criptografadas e regras de senha forte.
- **Isolamento dos dados:** cada usuário só acessa o próprio negócio.
- **Fechado por padrão:** qualquer funcionalidade nova exige login, a menos que seja explicitamente pública.
- **Perfis de acesso:** o módulo financeiro e o Pix ficam restritos a contas autorizadas.
- **Limite de tentativas** no login (contra descoberta de senha por força bruta) e nas funções de IA (contra abuso e custo).
- **HTTPS obrigatório** em produção.
- **Recuperação de senha segura:** o link expira em 2 horas, só vale uma vez e desconecta as sessões antigas; o sistema não revela se um e-mail tem cadastro.
- **Pagamentos:** o aviso da Abacate Pay só é aceito com um segredo compartilhado, e avisos repetidos não geram lançamentos duplicados.
- **Minimização de dados (LGPD):** o extrato bancário não é guardado, e dados pessoais dos clientes não são enviados à IA.
- **Credenciais** (chaves de API) ficam em variáveis de ambiente, nunca no código.

Para virar um produto comercial, seriam necessários, entre outros: política de privacidade e termos de uso, contas de pagamento individuais por empreendedor, auditoria de segurança e testes com usuários reais.

---

## 22. Escopo da prova de conceito

### 22.1 Entregue

- plataforma web responsiva, com página inicial pública (demonstração de Pix e calculadora de margem abertas ao visitante);
- cadastro de usuário (inclusive com Google) e recuperação de senha;
- cadastro do negócio;
- cadastro de produtos com custos, taxas, impostos, estoque e foto;
- cálculo de margem real e de preço sugerido;
- registro manual de entradas e saídas;
- importação de extrato bancário (OFX);
- cobrança Pix pela Abacate Pay, com confirmação automática;
- consolidação dos recebimentos e valores a receber;
- dashboard financeiro com calendário e evolução mensal;
- insights com IA;
- assistente financeiro com histórico;
- recomendações de marketing baseadas na margem real;
- geração de campanhas com IA;
- integração entre recomendação e criação de campanha.

### 22.2 Fora do escopo desta versão

- **Contas individuais de recebimento:** não há conta financeira própria para cada empreendedor.
- **Subcontas / contas conectadas:** cada empreendedor não conecta a própria conta de pagamento.
- **Marketplace financeiro:** o WageUp não custodia nem distribui valores de vários empreendedores.
- **Split de pagamentos.**
- **Open Finance:** sem conexão automática com contas bancárias.
- **BaaS:** o WageUp não pretende ser uma infraestrutura bancária.
- **Conciliação completa** entre Pix, maquininhas, bancos e outros provedores.
- **Emissão de nota fiscal e guias do MEI (DAS).**

### 22.3 Previsto no escopo inicial e não entregue

- **Metas financeiras.**
- **Totais separados por forma de pagamento** (Pix, dinheiro, cartão).
- **Geração de imagens** para campanhas.
- **Análise por dia/semana com comparação automática** (existe calendário diário e filtro por período, mas não uma comparação pronta entre semanas).

### 22.4 Limitações conhecidas

- Cobranças Pix centralizadas numa **conta de teste** (ver seção 23).
- **Um negócio por usuário**, sem colaboradores.
- **Não há registro de vendas por produto**: o sistema sabe a margem de cada produto, mas não quantas unidades vendeu. Perguntas como "qual produto vendeu mais?" ainda não têm resposta.
- O serviço gratuito de hospedagem "dorme" sem uso e leva cerca de 50 segundos para acordar.
- A plataforma não foi avaliada com usuários reais.

---

## 23. Limitação da integração de pagamentos e arquitetura futura

A integração com a Abacate Pay tem uma função específica no TCC: **validar tecnicamente o fluxo de criação e confirmação de pagamentos**.

Na prova de conceito, todas as cobranças vão para uma única conta de teste:

```text
WageUp ──► Abacate Pay ──► Conta de teste do projeto
```

Por isso o acesso ao Pix fica restrito a contas autorizadas. Isso **não é a arquitetura definitiva** do produto.

Numa versão multiusuário, cada empreendedor deveria ter ou conectar a própria conta de recebimento:

```text
                          ┌──► Conta do Empreendedor A
                          │
WageUp ──► Provedor ──────┼──► Conta do Empreendedor B
                          │
                          └──► Conta do Empreendedor C
```

Essa arquitetura não foi implementada por sua maior complexidade técnica, operacional e regulatória.

### Visão de futuro

O WageUp deve funcionar como uma **camada de inteligência sobre infraestruturas financeiras que já existem**, e não criar uma infraestrutura bancária própria. Possibilidades:

- contas conectadas e subcontas;
- múltiplos provedores de pagamento;
- Open Finance e integração com maquininhas;
- conciliação automática ampliada;
- análises financeiras mais avançadas.

O diferencial fica na **interpretação dos dados e no apoio à decisão**.

---

## 24. Critérios de sucesso

A prova de conceito é considerada funcional quando demonstra o fluxo completo:

```text
Cadastro                          ✅
   ↓
Produtos + custos                 ✅
   ↓
Recebimentos                      ✅  (Pix automático, manual e extrato)
   ↓
Consolidação financeira           ✅
   ↓
Dashboard                         ✅
   ↓
Análise                           ✅  (margem real, insights)
   ↓
Assistente                        ✅
   ↓
Recomendação                      ✅
   ↓
Ação de Produto/Marketing         ✅  (campanha gerada a partir da recomendação)
```

O fluxo principal foi demonstrado de ponta a ponta, em produção.

O objetivo não é entregar uma plataforma financeira completa, mas **validar o conceito** de uma ferramenta que conecta dados financeiros, inteligência e ações de crescimento.

---

## 25. Roadmap

### Fase 1 — TCC / prova de conceito

- [x] Cadastro de usuário
- [x] Cadastro do negócio
- [x] Cadastro de produtos
- [x] Cadastro de custos, taxas e impostos
- [x] Registro manual de recebimentos
- [x] Integração Pix
- [x] Confirmação automática de pagamentos
- [x] Dashboard
- [x] Indicadores financeiros e margem real
- [x] Assistente financeiro
- [x] Recomendações
- [x] Área de Produto e Marketing
- [x] Recursos de IA (texto)
- [x] Importação de extratos (OFX) — antecipado da Fase 2
- [ ] Metas
- [ ] Geração de imagens

### Fase 2 — Organização financeira do MEI (derivada da pesquisa)

- [ ] Classificação de cada lançamento como **negócio ou pessoal** (separação PF/PJ sem precisar de duas contas)
- [ ] **Pró-labore**: definir um "salário" do dono e acompanhar as retiradas
- [ ] **Agenda fiscal**: lembrete do DAS (dia 20) e da DASN-Simei (31/05)
- [ ] **Alerta do teto do MEI** (R$ 81 mil), considerando também o que entra no CPF
- [ ] **Previsão de caixa** para o mês seguinte
- [ ] **Relatório de faturamento** para pedir crédito
- [ ] Registro de vendas por produto
- [ ] Totais por forma de pagamento
- [ ] Extratos em CSV e PDF

### Fase 3 — Evolução da infraestrutura

- [ ] Contas conectadas / subcontas
- [ ] Recebimentos direcionados para cada empreendedor
- [ ] Conciliação automática ampliada
- [ ] Integração com maquininhas e outros meios de pagamento

### Fase 4 — Produto completo

- [ ] Open Finance
- [ ] Análises preditivas
- [ ] Metas avançadas
- [ ] Automação de campanhas
- [ ] Personalização das recomendações
- [ ] Integração com o WhatsApp
- [ ] Ecossistema ampliado de ferramentas para o microempreendedor

---

## 26. Resumo do projeto

O MEI é hoje a principal porta de entrada no empreendedorismo brasileiro: quase 15 milhões de registros ativos, na maioria gente que empreendeu por necessidade, depende do negócio para viver e controla o dinheiro no caderno, na planilha ou "de cabeça". Seis em cada dez misturam as finanças pessoais com as do negócio, e com isso não sabem quanto realmente lucram — enquanto a fiscalização sobre o faturamento tende a aumentar.

O **WageUp** é uma plataforma de apoio à gestão e ao crescimento desse público.

Seu **núcleo é financeiro**: reúne recebimentos (Pix automático, lançamentos manuais e extrato bancário) e custos, e mostra o **lucro real**, não só o faturamento.

Sobre essa base, o **Assistente Financeiro** interpreta os dados, responde perguntas em linguagem simples e aponta caminhos.

A área de **Produto e Marketing** transforma essas informações em ações práticas: o que divulgar, o que não divulgar e o texto pronto para postar.

O projeto não busca apenas responder:

> **"Quanto eu vendi?"**

Mas também:

> **"O que esses números significam?"**

E, principalmente:

> **"O que eu posso fazer agora?"**

> **Dados → Inteligência → Decisão → Ação → Crescimento**

---

## 27. Referências

> Antes de citar no trabalho final: confira cada link e a data de acesso, formate no padrão ABNT e, sempre que possível, cite a **fonte primária** (seção 27.2) em vez da matéria jornalística que a repercutiu.

### 27.1 Fontes citadas no texto

1. SEBRAE PR. *Crescimento dos pequenos negócios no Brasil em 2025.* <https://sebraepr.com.br/impulsiona/crescimento-dos-pequenos-negocios-no-brasil-em-2025/>
2. CONTÁBEIS. *Número de MEIs inadimplentes bate recorde em 2025.* <https://www.contabeis.com.br/noticias/70909/numero-de-meis-inadimplentes-bate-recorde-em-2025>
3. SEBRAE PR. *Abertura de pequenos negócios no Brasil cresce em 2025.* <https://sebraepr.com.br/impulsiona/abertura-de-pequenos-negocios-no-brasil-cresce-em-2025/>
4. SEBRAE PR. *MEI no Brasil: cenário econômico e perspectivas para 2024.* <https://sebraepr.com.br/impulsiona/mei-no-brasil-cenario-economico-e-perspectivas-para-2024/>
5. NEGÓCIOS SC. *Conheça o perfil dos donos de pequenos negócios no Brasil.* <https://www.negociossc.com.br/blog/conheca-o-perfil-dos-donos-de-pequenos-negocios-no-brasil/>
6. SEBRAE PR. *O perfil atual do microempreendedor individual no Brasil.* <https://sebraepr.com.br/impulsiona/o-perfil-atual-do-microempreendedor-individual-no-brasil/>
7. CONEXÃO TO. *6 em cada 10 empreendedores ainda misturam as finanças pessoais com as da empresa.* 20 ago. 2026. <https://conexaoto.com.br/2026/08/20/6-em-cada-10-empreendedores-ainda-misturam-as-financas-pessoais-com-as-da-empresa>
8. CONTÁBEIS. *Pequenos negócios ainda misturam finanças pessoais e da empresa.* <https://www.contabeis.com.br/noticias/74567/pequenos-negocios-ainda-misturam-financas-pessoais-e-da-empresa/>
9. SEBRAE PR. *Hábitos financeiros 2025.* <https://sebraepr.com.br/impulsiona/habitosfinanceiro2025/>
10. MUNDOCOOP. *Maioria dos pequenos empreendedores arrisca o negócio ao misturar contas pessoais e empresariais, revela Sebrae.* <https://mundocoop.com.br/economia-negocios/maioria-dos-pequenos-empreendedores-arrisca-o-negocio-ao-misturar-contas-pessoais-e-empresariais-revela-sebrae/>
11. TERRA. *Segundo Sebrae, 61% dos pequenos negócios misturam contas.* <https://www.terra.com.br/noticias/segundo-sebrae-61-dos-pequenos-negocios-misturam-contas,203f23200609bf4fe56d3cd87741c92cnwt9esju.html>
12. ACMINAS. *Empresários misturam contas de PF e PJ.* <https://acminas.com.br/imprensa/empresarios-misturam-contas-de-pf-e-pj/>
13. PODER360. *41,2% dos MEIs estão inadimplentes, diz Receita Federal.* <https://www.poder360.com.br/poder-empreendedor/412-dos-meis-estao-inadimplentes-diz-receita-federal/>
14. CONTÁBEIS. *Receita recebe apenas 38% das declarações do MEI.* <https://www.contabeis.com.br/noticias/76692/receita-recebe-apenas-38-das-declaracoes-do-mei/>
15. INFINITEPAY. *Como pagar DAS MEI atrasado.* <https://www.infinitepay.io/blog/pagar-das-mei-atrasado>
16. AGÊNCIA GOV. *Portal nacional centraliza emissão de nota fiscal de serviços para MEI.* set. 2023. <https://agenciagov.ebc.com.br/noticias/202309/portal-nacional-centraliza-emissao-de-nota-fiscal-de-servicos-para-mei>
17. INFOMONEY. *MEIs enfrentam dificuldades na emissão de nota fiscal nacional por instabilidades em plataforma.* <https://www.infomoney.com.br/minhas-financas/meis-enfrentam-dificuldades-na-emissao-de-nota-fiscal-nacional-por-instabilidades-em-plataforma/>
18. MAISMEI. *Como emitir a nova Nota Fiscal de Serviços Eletrônica (NFS-e): passo a passo.* <https://ajuda.maismei.com.br/hc/ajuda-da-maismei/articles/como-emitir-a-nova-nota-fiscal-de-servicos-eletronica-nfs-e-passo-a-passo>
19. SEBRAE PR. *Crédito ainda fora do alcance: desafios do MEI em 2025.* <https://sebraepr.com.br/impulsiona/credito-ainda-fora-do-alcance-desafios-do-mei-em-2025/>
20. SEBRAE RN. *Documentos para aprovação de crédito do MEI.* <https://blog.rn.sebrae.com.br/documentos-aprovacao-credito-mei/>
21. SEBRAE PR. *Pesquisa TIC 2025: transformação digital nos pequenos negócios.* <https://sebraepr.com.br/impulsiona/pesquisa-tic-2025-transformacao-digital-nos-pequenos-negocios/>
22. DATASEBRAE. *Transformação digital.* <https://datasebrae.com.br/transformacao-digital/>
23. CNDL. *O novo varejo brasileiro: entre a digitalização acelerada e a força das redes de negócios.* <https://cndl.org.br/varejosa/o-novo-varejo-brasileiro-entre-a-digitalizacao-acelerada-e-a-forca-das-redes-de-negocios/>
24. SEBRAE. *A taxa de sobrevivência das empresas no Brasil.* <https://sebrae.com.br/sites/PortalSebrae/artigos/a-taxa-de-sobrevivencia-das-empresas-no-brasil,d5147a3a415f5810VgnVCM1000001b00320aRCRD>
25. SEBRAE. *Sobrevivência de empresas 2020* (apresentação). <https://datasebrae.com.br/wp-content/uploads/2021/06/Apresenta%C3%A7%C3%A3o-Sobreviv%C3%AAncia_2020_Web_Final.pdf>
26. DIÁRIO DO COMÉRCIO. *Taxa de mortalidade de MEI é a maior em até cinco anos.* <https://diariodocomercio.com.br/legislacao/taxa-de-mortalidade-de-mei-e-a-maior-em-ate-cinco-anos/>
27. SERASA EXPERIAN. *O que muda para o MEI em 2025: novo limite e principais alterações.* <https://www.serasaexperian.com.br/conteudos/o-que-muda-para-o-mei-em-2025-novo-limite-e-principais-alteracoes/>
28. BUSCADOR NCM. *Nanoempreendedor na reforma tributária.* <https://buscadorncm.com.br/reforma/nanoempreendedor>
29. CONTÁBEIS. *Simples Nacional e MEI: como fica com a reforma tributária.* <https://www.contabeis.com.br/noticias/73791/simples-nacional-e-mei-como-fica-com-a-reforma-tributaria/>
30. SITE CONTÁBIL. *Quais serão as mudanças para o MEI em 2026.* <https://sitecontabil.com.br/noticias_empresariais/ler/quais-serao-as-mudancas-para-o-mei-em-2026->

### 27.2 Fontes primárias recomendadas

- SEBRAE. *Perfil do MEI 2024* (apresentação completa). <https://datasebrae.com.br/wp-content/uploads/2025/02/Apresentacao_Perfil-MEI_Sebrae_2024_ajustado_VF_11_02_25.pdf>
- SEBRAE. *Educação Financeira do MEI* (2018) — antiga, mas é a pesquisa específica sobre gestão financeira do MEI. <https://datasebrae.com.br/wp-content/uploads/2018/05/Educação_Financeira_MEI_2018_FINAL.pdf>
- SEBRAE. *Hábitos Financeiros dos Pequenos Negócios 2025.*
- SEBRAE. *Sobrevivência de Empresas* (2020).
- SEBRAE. *Pesquisa TIC 2025 — Transformação Digital nos Pequenos Negócios.*
- SEBRAE / FGV. *Sondagem Econômica do MEI* (mensal).
- FGV IBRE. *Análise do MEI* — visão crítica do programa. <https://ibre.fgv.br/sites/ibre.fgv.br/files/arquivos/u65/analise_do_mei_final.pdf>
- BRASIL. Lei Complementar nº 123, de 14 de dezembro de 2006 (Estatuto da Microempresa e do Simples Nacional, que institui o MEI).
- BRASIL. Lei Complementar nº 214, de 16 de janeiro de 2025 (regulamenta a reforma tributária sobre o consumo — IBS/CBS).
- BRASIL. Lei nº 13.709, de 14 de agosto de 2018 (Lei Geral de Proteção de Dados — LGPD).
- BANCO CENTRAL DO BRASIL. *Pix.* <https://www.bcb.gov.br/estabilidadefinanceira/pix>

---

*Funcionalidades marcadas como 🔜 são planejadas e não devem ser apresentadas no trabalho final como implementadas.*
