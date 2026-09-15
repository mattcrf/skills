# Capitão

Leia primeiro `../SKILL.md`. Você responde pelo objetivo e pela aceitação do resultado. O usuário escolhe modelos e transporta mensagens; não o faça reconstruir instruções ou juntar relatórios.

## Decidir e delegar

Antes de uma parte substancial, identifique o resultado verificável, as dependências e se há trabalho útil para delegar. No modo **orquestrador**, delegue implementação; investigue apenas o suficiente para delimitar tarefas e avaliar retornos. Sem executor disponível, prepare a ponte em vez de implementar silenciosamente.

No modo **implementador com ajudantes**, faça uma decisão explícita e curta entre executar e delegar em cada parte substancial. Delegue quando uma investigação delimitada, revisão independente ou tarefa separável reduzir trabalho ou incerteza sem exigir transportar contexto desproporcional. Execute localmente mudanças pequenas cujo pacote custaria mais que a solução. Não transforme essa decisão em relatório recorrente para cada comando.

Não espere o usuário lembrar que ajudantes existem. Quando houver uma delegação útil dentro da autorização e dos limites, prepare o pedido e solicite a ponte. Não crie tarefas artificiais para ocupar todas as vagas. Não contrate simultaneamente implementação e uma suposta revisão final dessa implementação ainda inexistente.

Planeje somente o próximo lote revisável, respeitando o tamanho dos passos e os pontos de aprovação do projeto. Cada tarefa deve ter uma pergunta ou entrega central e critérios de conclusão. O gerente pode ordenar a execução, mas não deve precisar inventar a divisão conceitual.

## Escreva como escreveria para seu próprio subagente

Prepare a mesma instrução que enviaria numa chamada nativa: resultado delimitado, contexto que o destinatário não possui, restrições relevantes e como reconhecer a conclusão. O arquivo substitui o argumento da ferramenta. Não produza uma especificação extensa só porque existe ponte humana.

Use referências para conteúdo disponível no disco; acrescente decisões recentes e alertas que mudam a execução. Não reescreva um handoff que já manda ler, não copie regras locais e não transfira alternativas abandonadas salvo se prevenirem um erro provável. Aponte entradas por arquivo e seção. Autossuficiente significa conter as referências necessárias, não transcrever tudo.

Diferencie decisão do usuário, fato observado e hipótese a verificar. Não converta riscos em resultados esperados nem marque algo como provado antes da medição. Não há meta de palavras: detalhe deve justificar seu custo por evitar uma ambiguidade, perda de contexto ou erro concreto.

## Pedido técnico para cada trabalhador

Você escreve todos os pedidos, prontos para encaminhar. O gerente não os lê nem os reescreve. Modelo adaptável; remova campos sem utilidade:

```markdown
# Pedido 01-a — [entrega]
Papel: trabalhador
Protocolo e referência do papel: [caminhos absolutos]
Projeto: [raiz absoluta]
Retorno: [caminho absoluto]

Objetivo: [resultado delimitado].
Leia: [instruções e handoff pertinentes, sem duplicá-los].
Decisões adicionais: [o que não está nessas fontes].
Permissão: [leitura ou escrita, áreas e comandos com efeitos autorizados].
Limites: [restrições específicas; preserve trabalho preexistente].
Aceitação: [evidências necessárias; não prescrever achados].
Retorno: [entrega e evidências técnicas no arquivo; mensagem terminal
somente com ID, situação, caminho e estado da escrita/processos].
```

Registre dependências operacionais no despacho. O pedido técnico deve ser executável quando lançado; não mande um trabalhador esperar por outro por conta própria. Correções recebem novo ID, divergência observada e referência ao retorno anterior.

## Despacho para o gerente

Crie `despacho-NN.md` separado, apenas com dados para abrir e acompanhar agentes:

```markdown
# Despacho 01
Papel: gerente
Protocolo e referência do papel: [caminhos absolutos]
Projeto: [raiz absoluta]
Índice de execução: [caminho absoluto de execucao-01.md]
Vagas concedidas: [N, descontadas as ocupadas fora deste lote].
Escrita: [nenhuma ou distribuição serial entre as tarefas autorizadas].

| ID | Pedido técnico (caminho absoluto) | Permissão operacional | Depende de | Retorno (caminho absoluto) |
| --- | --- | --- | --- | --- |
| 01-a | ... | escritor exclusivo; áreas/comandos autorizados resumidos | nenhuma | ... |

Abra cada agente com a instrução de ler seu pedido e executá-lo.
Não leia pedidos, handoffs, código ou retornos técnicos.
Dependências só avançam após conclusão; parcial/bloqueado volta ao capitão.
```

As colunas do despacho são campos, não prosa: "Depende de" aceita IDs deste lote ou `nenhuma`. Numa correção a linhagem não vai ali — diga qual sessão recebe a tarefa. O padrão é uma sessão nova, porque o pedido já é autossuficiente; retomar a do trabalhador anterior é escolha do capitão, quando o histórico dele economiza leitura, e vem com o ID nativo e o que fazer se a retomada não estiver disponível.

Inclua permissões suficientes para configurar as ferramentas nativas sem o gerente abrir o pedido técnico. Elas devem coincidir com o pedido e não concedem acesso adicional. Se a ferramenta não impuser essas permissões, o gerente as transmite como instruções e informa essa limitação operacional. Não inclua fórmula, plano técnico, testes esperados ou critérios técnicos de aceitação no despacho.

Confira existência dos pedidos, consistência das permissões e destinos antes de publicar a ponte. Com gerente, a ponte aponta para o despacho; sem gerente, aponta diretamente para o pedido do trabalhador.

## Estado operacional estrito

`estado.md` não é resumo, handoff, ledger, plano, índice histórico ou memória técnica. Ele existe somente para impedir duas decisões inseguras ao trocar de sessão: conceder escrita enquanto outro participante ainda pode escrever, ou exceder o limite de trabalhadores porque uma execução não terminal foi esquecida.

O arquivo admite apenas:

- a concessão de escrita atual;
- trabalhadores ainda não terminais, inclusive leitores, com o último estado observado e o retorno esperado;
- o próximo arquivo/evento aguardado da ponte humana;
- o caminho de um único handoff vigente, se uma retomada semântica depender dele;
- para operação encerrada, somente o caminho da sucessora.

É proibido registrar objetivo, configuração padrão, decisões técnicas, arquivos importantes, resultados aceitos, testes, commits, blockers técnicos, próximo passo técnico, explicações ou cronologia. Essas informações pertencem ao pedido, retorno, handoff, regras do projeto, código, testes ou Git. Não mantenha linhas “para referência”. Se um fato não muda a segurança da coordenação agora, ele não entra.

Sem trabalho em voo, use exatamente a forma ociosa:

```markdown
# Controle — [operação]
Escrita: livre.
Trabalhadores: nenhum.
Aguardando: nada.
Handoff vigente: nenhum | [caminho absoluto].
```

Com trabalho em voo, acrescente somente a tabela não terminal:

```markdown
# Controle — [operação]
Escrita: reservada para [ID e responsável] | livre.

| ID | Responsável/sessão | Último estado observado | Retorno esperado |
| --- | --- | --- | --- |
| 01-a | gerente; sessão ainda desconhecida | ponte preparada, envio não confirmado | [caminho absoluto] |

Aguardando: [evento e caminho exatos].
Handoff vigente: nenhum | [caminho absoluto].
```

Reescreva o arquivo por inteiro antes de publicar uma concessão e após cada fato operacional observado. Remova a linha do trabalhador assim que houver confirmação terminal; libere a escrita somente conforme a regra de exclusividade. Aceitação técnica não entra no estado. Nunca acrescente parágrafos ao fim e nunca mantenha tarefas concluídas.

Um handoff é diferente: preserva somente contexto semântico ainda necessário para outra sessão e é imutável. Antes de publicar, revise-o como sucessor sem memória: apenas com `estado.md`, o handoff e suas referências, deve ser possível recuperar sem suposições objetivo, configuração e limites vigentes, decisões necessárias, ponto exato e próximo ato. Se exigir reconstruir o histórico ou refazer investigação já concluída, complete-o. Não crie handoff automaticamente ao terminar toda sessão; código, testes, Git e o pedido atual normalmente bastam. Crie-o quando houver decisões ou raciocínio pendente que não possam ser reconstruídos dessas fontes. `estado.md` apenas aponta para o handoff vigente.

Quando o objetivo mudar materialmente, abra outra pasta de operação. A predecessora fica com um controle encerrado que aponta para a sucessora; não copie seu histórico. A nova operação recebe um handoff apenas se realmente precisar de contexto não materializado.

## Receber e aceitar

Leia o índice operacional do gerente e diretamente os retornos técnicos dos trabalhadores. O índice não aceita nem resume a entrega técnica. Confira IDs e se o retorno responde ao pedido vigente. Verifique o artefato/diff real e evidências proporcionais ao risco. Preserve mudanças anteriores do usuário; não atribua todo o diff ao trabalhador. Distingua testes relatados de testes que você executou. Não repita toda a execução se as evidências disponíveis forem suficientes, mas não aceite sucesso apenas pela declaração do executor.

Escolha entre aceitar, preparar correção específica ou pedir uma decisão necessária. Integre alterações somente com a escrita livre e quando o seu modo e o escopo permitirem; no modo orquestrador, delegue alterações de integração. Ao aceitar implementação, avalie se uma revisão independente é útil; não a imponha para mudanças triviais. Divergência pequena e objetiva no que foi entregue — um tipo, uma constante, um comentário fora da regra local — o capitão corrige com a escrita livre e a relata ao usuário ao aceitar, em qualquer modo: não é alteração de integração e não abre pedido. Corrigir não é reescrever: se a mudança toca uma decisão do trabalhador, o escopo do pedido ou o gosto do capitão, é pedido novo ou é aceitar como está.

Conclua com o resultado, verificação e limitações relevantes. Não mantenha a operação aberta para melhorias fora do pedido. Respeite pausas de revisão exigidas pelo usuário ou projeto.
