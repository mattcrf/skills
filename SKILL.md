---
name: orquestracao-manual
description: Coordenar agentes em ambientes distintos com ponte humana e pasta compartilhada, usando pedidos e retornos em arquivos. Use para operar esse fluxo como capitão, gerente ou trabalhador.
---

# Orquestração manual

Use as mesmas práticas de delegação que usaria ao invocar um subagente na própria harness. Este protocolo adapta o transporte, o acompanhamento e as permissões à ponte humana; não cria uma metodologia técnica alternativa nem exige pedidos mais longos.

O humano transporta mensagens curtas entre sessões. Os agentes compartilham arquivos, mas não memória de conversa nem acompanhamento automático. Reduza o trabalho da ponte e a duplicação de contexto. Não escolha nem recomende modelos: essa configuração pertence ao usuário e ao ambiente.

## Entrada e papéis

Leia este arquivo e somente a referência do papel recebido:

- [Capitão](references/capitao.md): planeja, delega e aceita resultados; pode operar como orquestrador ou implementador com ajudantes.
- [Gerente](references/gerente.md): abre e acompanha agentes nativos a partir de um despacho operacional, sem carregar ou consolidar conteúdo técnico.
- [Trabalhador](references/trabalhador.md): realiza uma tarefa delimitada.

Sem papel explícito, assuma capitão. Sem modo explícito, assuma orquestrador. Pedidos recebidos indicam o papel e os caminhos absolutos deste protocolo e da referência pertinente. As instruções do projeto continuam aplicáveis ao escopo de cada papel. O gerente segue as regras operacionais aplicáveis, sem assumir a leitura técnica exigida dos trabalhadores. Capitão e trabalhadores consultam as regras técnicas pertinentes quando ainda não as tiverem no contexto vigente; não releiam mecanicamente arquivos já carregados e inalterados. Não amplie autorizações do usuário.

## Início e configuração

Reutilize escolhas da conversa. Consulte `estado.md` somente para coordenação operacional ainda viva; ele não guarda objetivo, decisões técnicas ou contexto do projeto. Registre valores efetivos no pedido ou despacho que depende deles e não faça um questionário sobre informações já disponíveis. Na ausência de configuração, use os padrões abaixo e comunique-os brevemente:

```text
Papel: capitão
Modo: orquestrador
Delegação: ponte humana direta (ou com gerente, quando indicado)
Máximo de trabalhadores simultâneos: 2
Edição: um único escritor em toda a operação
Rodadas adicionais: permitidas dentro do escopo
Diretório de saídas: temp/tasks/ na raiz do projeto
```

O limite conta trabalhadores ativos em todos os ambientes e lotes da operação, inclusive agentes de leitura. Capitão e gerente coordenadores não contam como trabalhadores; não podem aproveitar essa exceção para criar trabalho paralelo além do limite. O número limita concorrência, não o total de chamadas. Não há orçamento monetário ou de tokens inferido. Respeite qualquer limite adicional definido pelo usuário.

Use delegação nativa somente se houver uma ferramenta real disponível e autorização aplicável. Não apresente uma sessão/task independente como subagente nativo, nem finja ter acionado ou acompanhado agentes. Na ausência da ferramenta, produza a ponte e devolva o controle ao usuário. Não espere em polling por uma resposta que depende de transporte humano.

## Arquivos da operação

O capitão escolhe uma pasta nova, com nome curto e único, em `temp/tasks/`, ou retoma a pasta explicitamente indicada. Não sobrescreva outra operação. Resolva a raiz do projeto local a partir do diretório de trabalho vigente.

```text
temp/tasks/<operacao>/
  estado.md          # controle operacional mutável, não histórico/contexto
  continuacao-01.md  # handoff do projeto, opcional, sem orquestração
  despacho-01.md     # operacional, para o gerente; omitido na ponte direta
  pedido-01-a.md     # técnico, escrito pelo capitão para o trabalhador
  retorno-01-a.md    # técnico, escrito pelo trabalhador
  execucao-01.md     # índice operacional escrito pelo gerente
```

Pedidos publicados, handoffs e retornos concluídos não são reescritos. Correções recebem novo ID e apontam para o anterior. Cada arquivo tem um responsável; não use relatórios compartilhados com múltiplos escritores. O capitão reescreve `estado.md` por inteiro a cada transição operacional e escreve todos os pedidos técnicos, handoffs e despachos. O gerente escreve somente o índice de execução; cada trabalhador escreve seu retorno técnico. Se a ferramenta não permitir salvar o retorno, o gerente pode preservar a resposta recebida em arquivo, sem interpretá-la, identificando essa exceção. Não solicite conteúdo técnico na mensagem terminal do trabalhador: apenas ID, situação, caminho do retorno e encerramento da escrita. A pasta compartilhada não é uma barreira de acesso; a separação economiza contexto, não garante isolamento. Quando houver escolha, abra trabalhadores sem herdar a conversa do gerente e forneça o caminho do pedido; não prometa isolamento que a ferramenta não oferece.

`estado.md` é o registro volátil que desambigua fatos impossíveis de inferir com segurança dos arquivos imutáveis: quem detém a escrita, quais trabalhadores ainda não são terminais e qual evento da ponte é aguardado. Ele pode apontar para um único handoff vigente, sem resumi-lo. Código, testes, Git, regras do projeto, pedidos, retornos e handoffs são as fontes do contexto técnico; não os copie para o estado.

## Exclusividade de escrita

É uma escolha deste protocolo: apenas um participante pode alterar código ou artefatos da implementação de cada vez, mesmo em arquivos diferentes. Vale para capitão, gerente e todos os trabalhadores. Relatórios de coordenação em caminhos exclusivos são a exceção.

O capitão concede a escrita a uma tarefa direta ou entrega ao gerente a autoridade de distribuí-la dentro de um lote. Enquanto essa concessão estiver ativa, o capitão não edita nem concede outra. O gerente serializa seus escritores e não compartilha a autoridade com outro gerente. Não crie gerentes aninhados; trabalhadores não delegam.

Registre a concessão antes de publicar a ponte. Publicado o pedido, considere a permissão reservada, mesmo sem confirmação de início. Só libere após retorno terminal que confirme que o agente parou de escrever, ou confirmação explícita de interrupção. Silêncio, fim de turno do capitão e tempo decorrido não liberam a permissão. Um arquivo de estado documenta o acordo; não é um bloqueio automático do sistema.

Leitores não editam implementação. Comandos que alteram saídas compartilhadas, builds, testes com geração ou processos persistentes exigem coordenação com o escritor; atribua-os à tarefa com escrita ou a uma tarefa exclusiva de validação. A permissão de salvar relatório não autoriza esses efeitos. Leitura durante edição pode observar estado transitório: marque conclusões dependentes dele como provisórias. Faça revisão final sobre estado estável, sem escritor ativo, e reavalie conclusões se os arquivos mudarem depois.

## Mensagens para a ponte

Prepare e confira os arquivos antes de responder. Entregue um destino e um único bloco copiável por destino, com caminhos absolutos reais e IDs já preenchidos:

```text
Leia "<caminho absoluto do pedido>" e execute as instruções.
```

Na volta:

```text
Leia "<caminho absoluto do retorno>" e avalie os resultados.
```

Identifique fora do bloco `Para o gerente`, `Para o trabalhador` ou `Para o capitão`. O pedido contém tudo de que o destinatário precisa para iniciar. Não repita seu conteúdo na conversa. Se houver bloqueio que exige decisão humana, acrescente uma frase objetiva com a decisão necessária. Atualizações exigidas pelo ambiente continuam válidas, mas devem ser curtas.

Sem gerente, forneça um bloco separado para cada sessão e explique a ordem somente quando houver dependência. Nunca peça ao usuário iniciar simultaneamente dois escritores. Com gerente, transporte um lote em uma única ponte e receba uma única ponte consolidada.

## Retomada e limites

Ao retomar como capitão, leia `estado.md` para descobrir somente a coordenação ainda viva. Leia os pedidos, despachos, retornos ou o handoff exato para os quais ele apontar e confira o estado real dos arquivos; não percorra o histórico da pasta. Como gerente, retome pelo despacho, índice operacional e estado nativo dos agentes; não carregue pedidos ou relatórios técnicos para reconstruir a execução. Não interprete ausência de retorno como ausência de agente ativo. Resolva permissões incertas antes de editar ou redistribuir. Não refaça trabalho aceito sem razão concreta.

Pedidos repetidos com o mesmo ID não autorizam execução duplicada. Se já houver retorno terminal, reutilize-o após conferir sua aplicabilidade; se houver execução possivelmente ativa, esclareça seu estado. Mudanças necessárias viram outro pedido.

Economize usando referências precisas, relatórios proporcionais e verificação focada. Não copie históricos, arquivos inteiros ou logs extensos que já estejam acessíveis. Não omita falhas para encurtar a resposta. Escrever custa vezes mais que ler, e o mesmo texto emitido duas vezes é o desperdício mais comum: campos de um retorno não se repetem entre si. `estado.md` segue o esquema estrito da referência do capitão; qualquer narrativa ou campo fora dele é defeito, mesmo que curto. Uma tentativa improdutiva exige mudança de estratégia; não reenvie a mesma tarefa indefinidamente. Se não houver próximo passo justificável, devolva o impasse ao capitão ou usuário.

## Uso sem instalação

Este protocolo é texto comum. Em qualquer ambiente com acesso aos arquivos, a mensagem inicial pode ser:

```text
Leia "C:\Users\mattc\Documents\orquestracao-manual\SKILL.md".
Atue como capitão no modo orquestrador, com ponte humana e gerente.
Use até 2 trabalhadores simultâneos e temp/tasks/ para as saídas.
Objetivo: [descreva a tarefa].
```

Adapte o caminho se mover a pasta. A descoberta automática como skill depende do ambiente; o protocolo não depende dela.
