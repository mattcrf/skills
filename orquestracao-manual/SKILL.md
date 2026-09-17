---
name: orquestracao-manual
description: Coordenar agentes em ambientes distintos com ponte humana e pasta compartilhada, usando pedidos e retornos em arquivos. Use para operar esse fluxo como capitão, gerente ou trabalhador.
---

# Orquestração manual

Adapte à ponte humana as mesmas decisões que tomaria com subagentes nativos. Os
agentes compartilham arquivos, mas não conversa nem acompanhamento automático.
Reduza o transporte e não escolha nem recomende modelos: isso pertence ao usuário
e ao ambiente.

## Papel

Leia este arquivo e somente a referência do papel recebido:

- [Capitão](references/capitao.md): planeja, delega e aceita; opera como
  orquestrador ou implementador com ajudantes.
- [Gerente](references/gerente.md): abre e acompanha agentes nativos sem ler ou
  consolidar conteúdo técnico.
- [Trabalhador](references/trabalhador.md): executa uma tarefa delimitada.

Sem papel explícito, assuma capitão; sem modo explícito, orquestrador. Capitão e
trabalhadores leem as regras técnicas pertinentes ainda ausentes do contexto; o
gerente segue apenas as regras operacionais aplicáveis. Não releia arquivos
inalterados já presentes nem amplie autorizações.

Pedidos para trabalhadores informam papel e caminhos absolutos deste protocolo e
da referência pertinente. O despacho informa apenas o papel, salvo pedido do
usuário por esses caminhos na sessão.

## Configuração

Reutilize escolhas da conversa; não pergunte pelo que já está disponível. Grave
valores efetivos no pedido ou despacho que deles depender. Sem configuração,
anuncie brevemente e use:

```text
Papel: capitão
Modo: orquestrador
Delegação: ponte humana direta (ou com gerente, quando indicado)
Máximo de trabalhadores simultâneos: 2
Edição: um único escritor em toda a operação
Rodadas adicionais: permitidas dentro do escopo
Diretório de saídas: temp/tasks/ na raiz do projeto
```

O limite abrange todos os trabalhadores ativos, inclusive leitores e lotes
distintos; capitão e gerente coordenadores não contam, mas não podem usar essa
exceção para excedê-lo. Ele limita concorrência, não chamadas. Não infira
orçamento e respeite limites adicionais do usuário. Use delegação nativa somente
com ferramenta real e autorização. Não apresente sessão ou task independente
como subagente, nem finja ter acionado ou acompanhado agentes; sem a ferramenta,
prepare a ponte e não espere por transporte humano em polling.

## Operação e autoria

O capitão resolve a raiz pelo diretório de trabalho e cria uma pasta curta e
única, ou retoma a indicada, sem sobrescrever outra operação:

```text
temp/tasks/<operacao>/
  estado.md          # controle operacional mutável
  continuacao-01.md  # handoff técnico opcional
  despacho-01.md     # do capitão para o gerente; omitido na ponte direta
  pedido-01-a.md     # do capitão para o trabalhador
  retorno-01-a.md    # do trabalhador
  execucao-01.md     # do gerente
```

Pedidos publicados, handoffs e retornos concluídos são imutáveis; correções usam
novo ID e apontam para o anterior. Cada arquivo tem um responsável: o capitão
escreve estado, pedidos, handoffs e despachos; o gerente, o índice de execução;
cada trabalhador, seu retorno. Se o trabalhador não puder salvá-lo, o gerente
pode preservar a resposta sem interpretar e identificando a exceção. Prefira
trabalhadores sem herdar a conversa do gerente e aponte o pedido; a pasta
compartilhada não fornece isolamento, portanto não prometa isso.

Enquanto a operação está viva, `estado.md` contém somente a concessão de escrita,
trabalhadores não terminais, evento aguardado e, se necessário, um handoff
vigente; encerrada, somente o caminho da sucessora. Contexto técnico fica em
código, Git, regras, pedidos, retornos e handoffs.

## Escritor exclusivo

Somente um participante altera implementação ou suas saídas por vez, mesmo em
arquivos diferentes. Relatórios de coordenação em caminhos exclusivos são a
exceção. O capitão concede escrita diretamente ou autoriza um gerente a
serializá-la; enquanto reservada, não edita nem concede outra. O gerente não
divide a autoridade com outro gerente; gerentes não se aninham e trabalhadores
não delegam.

Registre a reserva antes da ponte. Um pedido publicado já reserva a permissão;
silêncio, tempo ou fim de turno não a liberam. Libere-a somente após retorno
terminal que encerre a escrita e quaisquer processos capazes de escrever, ou
confirmação explícita de interrupção. O estado registra o acordo, mas não o impõe
tecnicamente.

Leitores não editam implementação. Build, teste com geração, saída compartilhada
ou processo persistente pertence ao escritor ou a uma validação exclusiva;
permissão para relatório não autoriza esses efeitos. A leitura durante edição é
provisória; revisão final exige estado estável e deve ser refeita se os arquivos
mudarem.

## Ponte

Confira e grave os arquivos antes de responder. Identifique fora do bloco `Para o
gerente`, `Para o trabalhador` ou `Para o capitão`; entregue então um único bloco
copiável por destino, com IDs preenchidos e caminhos absolutos reais, sem repetir
o arquivo. O pedido deve bastar para iniciar:

```text
Leia "<caminho absoluto>" e execute as instruções.
```

Na volta:

```text
Leia "<caminho absoluto do retorno ou índice>" e avalie os resultados indicados.
```

Sem gerente, use blocos separados e informe a ordem apenas quando houver
dependência; nunca peça ao usuário que inicie dois escritores simultaneamente.
Com gerente, envie e receba um único lote consolidado. Além do identificador,
acrescente fora do bloco apenas uma decisão humana necessária. Atualizações
exigidas pelo ambiente continuam válidas, mas devem ser curtas. Não inclua
conteúdo técnico na mensagem terminal do trabalhador: além do invólucro da ponte
exigido pelo papel, informe somente ID, situação, caminho do retorno e estado da
escrita/processos.

## Retomada e economia

Consulte `estado.md` apenas para coordenação ainda viva. Como capitão, leia os
arquivos exatos apontados e confira o estado real, sem percorrer o histórico;
como gerente, use despacho, índice e ferramentas nativas, sem ler conteúdo
técnico. Resolva permissões incertas antes de editar ou redistribuir.

Ausência de retorno não prova que um agente terminou. Não repita um ID nem refaça
trabalho aceito sem razão: reutilize retorno terminal ainda aplicável, esclareça
execução possivelmente ativa e dê novo ID a mudanças. Use referências e
evidências proporcionais, sem copiar arquivos, históricos ou logs acessíveis;
não repita informação entre campos de um retorno nem omita falhas. `estado.md`
obedece estritamente ao esquema do capitão; qualquer campo ou narrativa extra é
defeito. Após tentativa improdutiva, mude a estratégia e não reenvie a mesma
tarefa indefinidamente; sem próximo passo justificável, devolva o impasse.
