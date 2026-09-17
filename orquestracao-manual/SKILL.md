---
name: orquestracao-manual
description: Coordenar capitão, gerente e trabalhadores por arquivos compartilhados e ponte humana, com publicação e despacho validados pelo CLI incluído na skill.
---

# Orquestração manual

Use esta skill quando agentes trabalham em ambientes distintos e o usuário
transporta uma única mensagem entre o capitão e um gerente operacional. A pasta
compartilhada contém pedidos e retornos; o CLI incluído cria a operação, sela
pedidos e gera o despacho sem duplicar protocolo.

## Escolha o papel

Leia este arquivo e somente as referências do papel recebido:

- **Capitão:** leia [capitao.md](references/capitao.md) e
  [cli.md](references/cli.md). Define o trabalho, publica a cadeia e aceita ou
  rejeita o resultado.
- **Gerente:** leia [gerente.md](references/gerente.md). Abre e acompanha os
  agentes nativos descritos no despacho; não toma decisões técnicas.
- **Trabalhador:** leia [trabalhador.md](references/trabalhador.md). Executa um
  pedido publicado como scout, escritor ou verificador.

Sem papel explícito, assuma capitão. Não leia `manutencao/`, testes ou código do
CLI para operar a skill; a referência do CLI é a interface pública.

## Fluxo normal

Para uma mudança de implementação, o capitão publica uma cadeia de duas tarefas:

```text
escritor -> verificador independente -> capitão
```

Use um scout antes delas somente quando uma dúvida factual concreta impedir a
definição segura do pedido ou da aceitação. Não crie curador. Quatro ou mais
sessões técnicas exigem risco excepcional explicado pelo capitão; capacidade
disponível não é motivo para preencher vagas.

O capitão gera um despacho operacional e o usuário o entrega ao gerente. O
gerente executa todas as dependências que não exigem nova decisão do capitão e
devolve um único índice. O capitão lê os retornos indicados, confere código e
evidências e decide. O usuário escolhe modelos e transporta mensagens; nenhum
papel escolhe fornecedor por conta própria.

## Garantias

- Um único trabalhador pode modificar a implementação ou suas saídas por vez.
- Scout e verificador são somente leitura da implementação.
- Pedidos publicados, despachos gerados e retornos terminais são imutáveis;
  correções recebem novo ID.
- Resultado parcial ou bloqueado não libera dependências e volta ao capitão.
- Gerente coordena sessões, mas não lê nem resume conteúdo técnico.
- Trabalhadores não delegam e não ampliam permissão ou escopo.
- O capitão continua responsável por decomposição, julgamento do diff e aceite.
- Commits, ações destrutivas e efeitos externos continuam sujeitos ao pedido e
  às regras do projeto.

Tamanho de texto é métrica, não autorização para cortar informação. O CLI marca
um pedido acima da meta como `budget=over`, mas publica normalmente. Nunca entre
em ciclos de compressão nem sacrifique requisitos, evidência ou clareza para
atingir uma contagem.

## Operação compartilhada

Novas operações usam o formato criado por `om op init`, fora do repositório
alvo. Quando o usuário não indicar outro lugar, o capitão não pergunta nem
inventa um caminho: o CLI cria `<id>` na raiz operacional padrão
`%USERPROFILE%\Documents\skills\temp\ops` no Windows. Um caminho explícito
continua podendo substituir o padrão.

O capitão escolhe um ID curto e específico para a nova operação. O caminho
absoluto criado pelo CLI torna-se canônico e é propagado, sem ser redigitado:
o despacho o entrega ao gerente; o gerente o entrega a cada trabalhador; cada
pedido publicado contém o mesmo caminho e o retorno absoluto.

Estrutura:

```text
<operação>/
  operation.toml
  tasks/             # pedidos publicados e selados
  results/           # retornos dos trabalhadores
  events.jsonl       # publicação append-only
  dispatch*.md       # despachos gerados para o gerente
  execution*.md      # índices escritos pelo gerente
  .scratch/drafts/   # rascunhos editáveis, ignorados
  .cache/            # lock local, ignorado
```

Cada arquivo tem um responsável: o CLI publica `operation.toml`, `tasks/`,
`events.jsonl` e despachos; cada trabalhador escreve somente seu retorno e os
efeitos autorizados no projeto; o gerente escreve somente o índice indicado; o
capitão edita apenas rascunhos ainda não publicados.

O formato anterior em `temp/tasks/` continua legível como histórico, mas não é
modelo para uma operação nova. Não crie `estado.md`, despacho ou pedido manual
quando o CLI puder produzi-lo.

## Ponte

Depois de conferir os arquivos, entregue um único bloco copiável:

```text
Para o gerente
Leia "<caminho absoluto do despacho gerado>" e execute as instruções.
```

Na volta:

```text
Para o capitão
Leia "<caminho absoluto do índice de execução>" e avalie os retornos indicados.
```

Não copie conteúdo técnico para a ponte. Atualizações exigidas pela harness
continuam válidas, mas devem ser curtas.
