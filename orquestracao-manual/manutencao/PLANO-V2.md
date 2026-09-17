# Orquestração v2 — plano de desenho e validação

Status: candidato revisado para revisão

Base empírica: operação `lua-translator-02`

Premissa econômica: tokens e atenção do capitão são escassos; capacidade de
gerente, scouts, escritores e verificadores baratos é abundante até cerca de três
vezes o consumo atual e três agentes simultâneos.
Objetivo principal: reduzir de forma substancial e mensurável o consumo de contexto
e produção textual do capitão, usando trabalhadores baratos para preparar, executar
e pré-revisar o trabalho, sem perder as garantias que impediram erros reais.

## 1. Critério de sucesso

Este trabalho não será considerado bem-sucedido por ter mais automação ou uma
estrutura mais sofisticada. Será bem-sucedido somente se um replay representativo
da operação `lua-translator-02`, seguido por uma operação de natureza diferente,
demonstrar:

1. redução forte da entrada e da saída textual do capitão;
2. preparação, implementação e pré-revisão transferidas aos agentes baratos sempre
   que não exigirem decisão do capitão;
3. pedidos e pacotes de decisão muito menores;
4. eliminação da escrita manual de despachos, índices de execução e estado;
5. menos artefatos duráveis e nenhuma duplicação de evidência pesada;
6. preservação das garantias: papéis claros, escritor exclusivo, pedido e retorno
   imutáveis, revisão técnica pelo capitão e rastreabilidade;
7. impossibilidade, ou detecção automática antes do despacho, dos estados inválidos
   já observados;
8. ausência de regras centrais específicas do tradutor Lua, NeoLua, rAthena ou de
   qualquer linguagem, banco, harness ou projeto particular.

Uma ferramenta que não mova ao menos uma dessas métricas não entra no produto.
Reduzir travessias humanas é desejável, mas secundário diante do custo do capitão e
do acesso a agentes externos baratos.

## 2. Linha de base medida

### 2.1 Contexto fixo da skill

A primeira etapa já realizada reduziu a leitura inicial do capitão de 3.126 para
2.080 palavras: **33,5%**. Esta é a nova linha de base, não o fim da otimização.
A fixture complementar `manutencao/benchmarks/lua-translator-02-phase-a.json`
sela, com proveniência, as revisões e o algoritmo dessa contagem, além da
topologia da ponte, da proliferação e das cápsulas.

### 2.2 Artefatos de coordenação

| Grupo | Arquivos | Linhas | Palavras | Bytes |
| --- | ---: | ---: | ---: | ---: |
| pedidos | 28 | 3.401 | 22.730 | 173.896 |
| retornos | 28 | 2.918 | 25.220 | 203.457 |
| despachos | 25 | 434 | 3.428 | 32.749 |
| execuções | 25 | 249 | 1.518 | 12.089 |
| continuações | 3 | 244 | 1.600 | 10.976 |
| **total** | **109** | **7.246** | **54.496** | **433.167** |

Médias relevantes:

- pedido: 121,5 linhas, 811,8 palavras e 6.210,6 bytes;
- retorno: 104,2 linhas, 900,7 palavras e 7.266,3 bytes;
- despacho: 17,4 linhas e 1.310 bytes;
- índice de execução: 10 linhas e 483,6 bytes.

As repetições confirmam que parte relevante do pedido é protocolo: o caminho do
projeto aparece nos 28 pedidos; referências da skill, regras de leitura, caminhos
de arquivos, permissões e comandos reaparecem muitas vezes. Nos retornos, estado
de encerramento, processos persistentes, pendências, arquivos alterados e comandos
de teste são em boa parte dados que uma ferramenta pode coletar.

### 2.3 Travessias humanas

Houve 25 ciclos pela ponte: 25 envios ao gerente e 25 devoluções ao capitão,
aproximadamente **50 transportes humanos**. Dos 25 despachos:

- 24 continham uma única tarefa;
- 1 continha duas tarefas paralelas;
- 26 das 28 tarefas passaram pelo gerente; duas foram anteriores ou diretas.

Isto impõe uma conclusão: compactar o arquivo de despacho não reduz materialmente
as viagens. No modo manual, uma cadeia de decisões sequenciais ainda exige que
alguém acorde cada lado. Uma redução substancial do item 4 exige mudar a topologia,
não somente o formato.

### 2.4 Proliferação e duplicação

A pasta da operação terminou com 417 arquivos e 32.831.762 bytes (31,31 MiB).
Havia:

- 34 JSONs na raiz da operação, somando 19.007.360 bytes;
- três projetos NeoLua;
- nove diretórios de baseline identificados na inspeção;
- resultados raw de 3,3 a 6,9 MiB;
- 111 Markdown na raiz ou árvore da operação.

Pedidos e retornos são caros em contexto e trabalho humano, mas representam pouco
do volume em disco. A redução de bytes depende de tratar evidência e scratch de
forma diferente; não deve ser atribuída falsamente à compactação dos textos.

### 2.5 Assimetria econômica dos agentes

Condição fornecida pelo proprietário:

- o capitão é, por ampla margem, o agente mais caro;
- DeepSeek e Muse Spark entregam trabalho adequado por custo muito baixo, mas não
  podem ser invocados nativamente por Claude ou GPT;
- gerente e trabalhadores podem consumir duas ou até três vezes o volume atual sem
  pressionar o orçamento;
- há capacidade prática para até três agentes baratos simultâneos;
- GPT Luna também é um trabalhador barato válido quando a delegação nativa trouxer
  vantagem líquida.

Portanto, custo total de tokens não é a função objetivo correta. A função objetivo
é minimizar **tokens e atenção do capitão**, sob qualidade constante ou maior. É
aceitável aumentar deliberadamente o trabalho barato para reduzir a leitura,
redação e investigação do capitão.

Os arquivos da operação permitem estabelecer somente limites inferiores:

- o capitão produziu ao menos 22.730 palavras em pedidos;
- recebeu ao menos 25.220 palavras em retornos;
- código, diffs, logs, mensagens de chat e releituras de contexto não estão
  integralmente contabilizados nesses 47.950 termos.

A Fase A deve medir esses componentes por papel em vez de somar todos os agentes em
um único número, que esconderia justamente a economia procurada.

### 2.6 Limite de generalização

`lua-translator-02` é benchmark e conjunto de incidentes conhecidos, não modelo de
domínio. NeoLua, corpus, scripts rAthena e snapshots são exemplos de `harness`,
`dataset`, `baseline` e `artifact`; esses conceitos devem funcionar igualmente para
C#, C++, documentação, diagnóstico, pesquisa e outros repositórios. Nenhuma
abstração entra no núcleo se não puder ser nomeada sem vocabulário do tradutor.
Cada tarefa declara somente se é `read-only` ou `mutating`: lease de escrita,
baseline de mutação e diff são obrigatórios apenas no segundo caso.

## 3. Garantias que permanecem

O desenho v2 preserva:

- capitão responsável por decomposição, decisão e aceite técnico;
- nenhum agente barato nem ferramenta aceita código em nome do capitão;
- um único escritor por superfície de código;
- leitores paralelos somente quando seus escopos não escrevem implementação;
- pelo menos uma verificação independente após toda implementação; duas quando o
  risco, o tamanho ou a alteração de testes cruzar o limiar configurado;
- pedido publicado e resultado final imutáveis;
- resultado parcial ou bloqueado volta ao capitão;
- nenhuma decisão técnica transferida ao gerente;
- alterações no projeto sempre delimitadas e comparáveis;
- evidência suficiente para auditar por que uma tarefa foi aceita;
- divergência entre implementador e verificadores sempre visível ao capitão;
- ações destrutivas, commits e integrações continuam dependendo da autorização
  definida pelo usuário e pelas regras do projeto.

O objetivo é retirar cerimônia, não controle.

## 4. Tese do novo desenho

A v2 terá um **plano de controle local único**, acessado por um único CLI, com um
pool de agentes baratos e adaptadores de transporte. O conteúdo técnico continuará
em arquivos pequenos e legíveis; estado, validação, métricas e evidência mecânica
serão gerados. O capitão verá um pacote de decisão, não a descarga bruta da operação.

```text
 intenção do usuário
         |
         v
 capitão: decisão curta
         |
         v
 +---------------------------------------------------+
 | om: estado, escopos, leases, evidência e métricas |
 +---------------------------------------------------+
         |
         +--> scout barato: investiga e rascunha a tarefa
         +--> escritor barato: implementa
         +--> verificador A: confere critérios, diff e checks --+
         +--> verificador B: procura falhas e omissões ----------+--+
                                                                  |
                                     pacote de decisão compacto <-+
                                                                  |
                                                                  v
                                                    capitão: inspeciona e decide

 transporte dos agentes: bridge externo | nativo | broker futuro
```

`om` é o nome de trabalho do comando. Não haverá uma coleção de scripts públicos:
um executável com subcomandos, uma biblioteca interna e um formato versionado.

Os papéis baratos são capacidades, não sessões fixas:

- `scout`: pesquisa contexto, identifica superfícies e propõe tarefa/aceitação;
- `writer`: único agente autorizado a modificar a superfície concedida;
- `verifier`: reproduz checks e confronta critérios com o diff;
- `adversarial reviewer`: procura regressões, omissões e testes enganosos.

Não haverá `curator` inicial. Se a necessidade for demonstrada depois, ele poderá
ordenar ou anotar, nunca suprimir achados.

O limite inicial é três agentes baratos simultâneos. Eles podem executar etapas
diferentes ou análises redundantes, desde que somente um possua a lease de escrita.
Não é obrigatório ocupar as três vagas: paralelismo sem hipótese de ganho também é
desperdício, ainda que barato.

## 5. Separação estrutural

### 5.1 Repositório da skill

`C:\Users\mattc\Documents\skills\orquestracao-manual` conterá somente:

- protocolo e referências dos papéis;
- implementação do CLI;
- esquemas, testes e migrações;
- documentação de manutenção;
- fixtures pequenas para replay e benchmark.

As cópias instaladas em `.codex` e `.claude` continuam sendo destinos gerados ou
sincronizados, nunca a fonte de verdade.

### 5.2 Repositório de operações

O estado vivo não ficará nem no repositório da skill nem em `temp/` do projeto.
Será criado um repositório Git separado, por exemplo:

```text
C:\Users\mattc\Documents\orquestracoes\
  ops\
    ro-build-simulator\
      lua-translator-03\
        operation.toml
        contexts\
          004.md
        tasks\
          013-a.md
        results\
          013-a.md
        evidence\
          caso-excepcional.txt
        events.jsonl
        closure.md
        .scratch\
        .cache\
```

Princípios:

- `operation.toml` guarda uma vez raiz do projeto, backend, perfis de permissão,
  comandos recorrentes, limites e política de retenção;
- o mesmo manifesto declara pools por capacidades, custo relativo e concorrência,
  separando papel (`scout`, `writer`, `verifier`) de fornecedor ou modelo;
- `contexts/NNN.md` são snapshots imutáveis das decisões duráveis específicas da
  operação; `operation.toml` indica somente o snapshot atual;
- `tasks/` e `results/` são pequenos, humanos, publicados e imutáveis;
- `events.jsonl` é a fonte append-only das transições de estado, escrita apenas
  pelo CLI;
- `events.jsonl` também concentra metadados mecânicos comuns de checks e artefatos;
- `evidence/` só existe para uma evidência durável excepcional que não caiba no
  resultado ou no log de eventos; não há sidecar por tarefa por padrão;
- `.scratch/` guarda logs, raw, cópias temporárias e sondas; é ignorado pelo Git;
- `.cache/` contém locks locais e, somente se desempenho medido justificar, índices
  regeneráveis; também é ignorado;
- `closure.md` é gerado no encerramento e reúne resultado, decisões, pendências e
  métricas finais.

O Git versiona o plano de controle textual. Inicialmente, `status`, `inbox` e
métricas leem `events.jsonl` diretamente. SQLite só poderá ser acrescentado como
índice regenerável após gargalo medido; nunca será fonte canônica nem binário opaco
no histórico.

### 5.3 Projeto alvo

O projeto alvo volta a conter apenas código e artefatos próprios. A operação o
referencia por uma raiz declarada uma vez. Caminhos de tarefa são relativos à raiz.

Para projetos Git haverá dois modos:

- `worktree`: preferido para uma operação isolada iniciada de um commit limpo;
- `in-place`: compatibilidade quando a tarefa precisa partir da árvore de trabalho
  atual ou de alterações ainda não commitadas.

O CLI nunca fará commit, merge, stash, reset ou remoção no projeto sem uma política
explicitamente autorizada para a operação. No modo `in-place`, registra o estado
inicial e detecta alterações alheias; no modo `worktree`, ganha isolamento e uma
comparação naturalmente barata.

O efeito da tarefa é uma capacidade explícita:

- `read-only`: não adquire lease de implementação nem exige diff; entrega conclusões
  ancoradas nas fontes, checks e snapshots consultados;
- `mutating`: exige escritor exclusivo, estado inicial reproduzível, diff e
  conferência dos caminhos efetivamente alterados.

Os dois efeitos compartilham publicação, evidência, verificação e decisão. Isso
mantém diagnósticos, pesquisa e documentação não mutante como casos de primeira
classe sem inventar novos papéis.

## 6. Modelo de tarefa enxuto

Uma tarefa combina front matter TOML pequeno com corpo Markdown. Ela referencia
um perfil, em vez de repetir permissões, caminhos e comandos comuns.

```markdown
+++
id = "013-a"
kind = "writer"
effect = "mutating"
profile = "translator-writer"
context = 4
depends = []
+++

## Objetivo

Implementar `switch` com grupos de casos sem duplicar o corpo gerado.

## Delta técnico

- preservar a ordem de avaliação;
- aceitar somente os nós já enumerados na análise 012-b.

## Aceitação específica

- caso 410028 compila na sonda;
- snapshot esperado permanece legível.
```

O perfil `translator-writer`, definido uma vez em `operation.toml`, resolve:

- arquivos e diretórios graváveis;
- fontes somente leitura;
- regras do projeto que precisam ser lidas;
- checks recorrentes;
- limites de processos e artefatos;
- proibição ou permissão de commit.

O comando `om task show 013-a --role worker` apresenta apenas a visão resolvida
necessária. Não materializa outro arquivo longo e não copia o conteúdo integral de
AGENTS, skill ou contexto: aponta para as fontes canônicas que o agente deve ler.
O campo `context = 4` sela a tarefa contra `contexts/004.md`; uma decisão nova cria
`005.md` em vez de alterar retroativamente o significado de tarefas publicadas.

O capitão não precisa redigir esse arquivo do zero. O fluxo preferido é:

1. capitão registra intenção, restrições e eventual decisão já tomada em poucas
   linhas;
2. um ou dois scouts baratos inspecionam projeto e fontes e propõem objetivo,
   superfícies, riscos e aceitação;
3. o CLI confronta os rascunhos, destaca divergências e monta uma proposta;
4. o capitão aprova ou corrige somente as decisões, escopo e critérios relevantes;
5. `task publish` sela a versão final.

Pesquisa e redação são delegadas; responsabilidade e autorização não são.

Meta para o **delta canônico da tarefa**: até 2.000 bytes e 250 palavras em média.
Essa meta reduz o que o capitão precisa aprovar e o que se repete no histórico. A
visão resolvida entregue ao trabalhador pode ser maior ao incorporar referências,
pesquisa dos scouts e contexto necessário; seu tamanho é medido, mas não comprimido
às custas da qualidade.

## 7. Resultado e pacote de decisão do capitão

### 7.1 Captura do escritor

Para uma tarefa `mutating`, o escritor não redigirá novamente fatos que o computador
conhece:

1. `om task start 013-a` adquire a lease de escrita e registra Git/arquivos iniciais;
2. `om check 013-a -- <comando>` executa checks autorizados, mede duração e salva o
   log bruto em `.scratch/`;
3. o escritor registra somente raciocínio não inferível: resultado, decisões,
   limitações e achados fora do pedido;
4. `om task finish 013-a --notes <arquivo>` coleta diffs, arquivos alterados,
   checks, tempos, processos rastreados e estado do repositório;
5. o CLI valida o escopo e gera `results/013-a.md`; metadados detalhados entram no
   evento correspondente, sem criar um sidecar por tarefa.

Cada check guarda comando normalizado, exit code, duração, hash, tamanho e caminho
do log. O CLI compara os caminhos realmente alterados com o perfil concedido.
Alteração fora do escopo impede `complete` e transforma o resultado em
`needs-review`. Também diferencia “nenhum processo iniciado por `om` permanece
ativo” da alegação impossível de provar de que não existe qualquer processo externo.
Uma tarefa `read-only` usa a mesma captura para fontes, checks e notas, mas não
adquire lease de implementação nem fabrica baseline ou diff inexistente.

### 7.2 Pré-revisão barata e independente

O retorno do escritor não vai diretamente ao capitão. Após a lease de escrita ser
liberada:

1. um verificador barato confronta cada critério com diff, arquivos e checks;
2. um segundo agente, quando exigido pelo perfil de risco, procura regressões,
   pressupostos falsos, testes enfraquecidos e itens fora do pedido;
3. os verificadores não herdam a conclusão do escritor como fato; recebem o pedido,
   o estado inicial, o diff e a evidência;
4. cada achado recebe ID imutável e usa um esquema curto: severidade, afirmação,
   âncora exata, critério afetado, confiança e ação sugerida;
5. o CLI une dados objetivos e só colapsa achados estritamente equivalentes,
   preservando a relação entre todos os IDs de origem e a representação resultante;
6. desacordo, baixa confiança ou equivalência ambígua é `fail-open`: permanece
   explícito e nunca é rebaixado por ser minoritário.

Três agentes baratos podem ser empregados sem três escritores: por exemplo, um
scout em fonte externa, um escritor e um leitor de baseline durante a execução; ou
dois revisores independentes após o escritor terminar.

### 7.3 Pacote de decisão

O capitão recebe uma visão própria, não o retorno bruto:

- decisão solicitada e estado da tarefa;
- matriz requisito -> evidência -> veredito dos verificadores;
- mapa curto das mudanças e riscos;
- checks, duração, falhas e evidência ausente;
- achados deduplicados, divergências e incertezas;
- âncoras clicáveis para os hunks de maior risco;
- hash e caminho do diff completo para inspeção livre;
- itens fora do pedido, separados;
- recomendação de profundidade: diff completo, hunks de risco ou spot-check.

O pacote inclui uma tabela `finding-id -> representação`, cobrindo todo achado dos
verificadores. Um curador futuro pode ordenar, agrupar ou anotar essa tabela, jamais
suprimir IDs ou resolver semanticamente um desacordo em nome do capitão.

A recomendação não limita o capitão. Antes do dogfood, revisão ampliada é acionada
por condições observáveis: critério sem evidência independente; verificador incapaz
de emitir veredito; qualquer desacordo; check esperado ausente ou falho; alteração em
teste; caminho alterado fora da superfície prevista; ou arquivo/hunk modificado que
nenhum verificador examinou. Limiares de linhas/arquivos e perfis de caminhos
sensíveis podem ser conservadores e configuráveis, mas precisam ser mecânicos. Só
podem ser afrouxados com dados de dogfood. O objetivo é remover procura, transcrição
e leitura redundante, nunca ocultar código necessário à decisão.

O resultado do escritor não recebe teto rígido: pode crescer até o orçamento barato
da operação quando detalhe adicional ajudar os verificadores. Ele apenas não repete
dados mecânicos já capturados. A meta do pacote entregue ao capitão é **até 200
palavras em média**, excluindo código que ele deliberadamente abrir. Logs e raw não
contam como texto do pacote, mas entram separadamente na métrica de scratch.

### 7.4 Cápsula de retomada do capitão

`om resume --role captain` gera, sem editar a fonte canônica, uma cápsula contendo:

- objetivo e snapshot de contexto ativo;
- últimas decisões aceitas e seus hashes;
- tarefas em execução, bloqueadas ou aguardando decisão;
- estado Git relevante e leases;
- riscos, divergências e próxima decisão concreta;
- links para detalhes, sem incorporá-los por padrão.

Meta: até **300 palavras**. Após compactação ou troca de sessão, o capitão lê a
cápsula e somente as fontes cujo hash mudou. Isso não tenta contornar uma regra da
plataforma que obrigue reler a skill; reduz a reconstrução da operação. Quando a v2
for comprovada, a referência do capitão deve conter apenas invariantes e decisões,
enquanto instruções operacionais extensas podem ficar com trabalhadores baratos.

## 8. Máquina de estados e invariantes

Estados mínimos:

```text
draft -> ready -> running -> returned -> verifying -> captain-review -> accepted
                     |                         |              |             |
                     |                         |              +-> revision -+
                     +-> partial | blocked ----+                            v
                                                                        closed
```

Transições são comandos, não edições manuais. `om doctor` rejeita ou aponta:

- ID duplicado, malformado ou divergente do nome do arquivo;
- caminhos inexistentes ou fora das raízes permitidas;
- resultado que não corresponde a tarefa publicada;
- dependência ausente, cíclica ou ainda não aceita;
- duas leases de escrita sobre superfícies sobrepostas;
- leitor com permissão de implementação;
- resultado terminal sem checks ou campos obrigatórios;
- alteração real fora da concessão;
- handoff apontando para contexto ou commit obsoleto;
- arquivo publicado alterado depois do hash registrado;
- estado derivado diferente do log de eventos;
- scratch acima da política de retenção;
- quando o backend declarar suporte a heartbeat, sessão ativa sem heartbeat ou
  encerramento conforme a política desse backend.

`estado.md`, índices de execução e handoffs deixam de ser fontes editáveis. `om
status` os calcula de `events.jsonl`; uma visão Markdown pode ser gerada para
leitura, mas é descartável. Assim, o estado inválido observado anteriormente não é
apenas “menos provável”: não pode ser publicado pelo caminho normal.

Para suportar agentes paralelos no mesmo diretório, toda transição usa lock de
arquivo do sistema, gravação temporária + substituição atômica quando aplicável e
`fsync` antes de liberar o lock. Cada evento recebe sequência monotônica, hash do
evento anterior, papel, tarefa e hash do payload. O encadeamento detecta edição ou
truncamento acidental; ele não pretende ser um mecanismo criptográfico de confiança
contra um operador malicioso.

Na Fase B, o núcleo valida somente leases e transições locais. Heartbeat e detecção
de sessão obsoleta entram com o backend na Fase E, quando podem ser testados de forma
realista.

## 9. Transporte como decisão econômica

O transporte não define a qualidade do agente. A v2 escolhe backend por capacidade,
qualidade observada, custo do trabalhador, custo induzido no capitão e latência.
Reduzir cliques não justifica trocar DeepSeek ou Muse Spark por um agente mais caro
se a troca não reduzir o custo total do capitão ou melhorar o resultado.

### 9.1 Backend `bridge` — acesso econômico a agentes externos

A ponte com gerente deixa de ser tratada como dívida a eliminar. Ela é o adaptador
que disponibiliza agentes externos baratos que GPT e Claude não invocam nativamente.
O gerente permanece estritamente operacional e não lê conteúdo técnico.

Enquanto o plano de controle ainda não instalar ou resolver o protocolo por conta
própria, todo despacho do backend `bridge` inclui por padrão os caminhos absolutos da
fonte canônica do protocolo e da referência do gerente. O conteúdo não é duplicado no
despacho. Esse pequeno custo de leitura recai no agente mais barato e evita depender
de uma skill instalada ou de contexto implícito no ambiente externo. Versão ou hash
esperado poderão ser acrescentados quando a publicação automatizada existir.

A unidade de transporte da ponte é um **segmento executável da cadeia**, não uma
tarefa isolada. O capitão publica antecipadamente todas as tarefas independentes ou
dependentes que não exigem nova decisão técnica; o gerente inicia as prontas, desperta
para liberar sucessoras, aguarda o segmento terminar e devolve um índice consolidado.
O segmento acaba antes de qualquer bifurcação que exija arquitetura, mudança de
escopo, adjudicação de achado ou aceite de código pelo capitão. Sessões de agentes e
viagens humanas são medidas separadamente: uma cadeia pode conter várias sessões e
uma única ida e volta pela ponte.

Não haverá arquivos de despacho e execução escritos à mão. A mensagem pode ser
estável:

```text
No repositório de operações, execute: om manager run <operação>
```

O gerente consulta tarefas `ready`, abre até três sessões permitidas, registra IDs e
encerra quando não houver trabalho executável. O capitão consulta `om inbox`, que só
libera tarefas cujo pacote de decisão esteja pronto.

Este modo ainda deve eliminar os 50 arquivos manuais e reduzir o payload da ponte.
A contagem de ciclos será medida, mas não é gate primário. Ela cai naturalmente
quando há scouts ou verificadores independentes no mesmo lote; não se fabricará um
lote para adiar uma decisão que pertence ao capitão.

### 9.2 Backend `native` — trabalhador adicional, não padrão automático

Quando GPT Luna ou outro subagente nativo oferecer a melhor combinação, o capitão
pode delegar diretamente. O mesmo plano de controle registra IDs e resultados; o
papel e as garantias são idênticos aos do backend externo.

O backend nativo pode levar os transportes humanos a zero, mas só vence quando:

- produz qualidade suficiente para o papel;
- reduz contexto, espera ou trabalho do capitão;
- não sacrifica uma opção externa muito mais barata sem benefício compensatório.

É válido misturar backends na mesma operação: scout externo, escritor externo e
verificador Luna, por exemplo. O scheduler não escolhe modelo sozinho no primeiro
release; aplica uma política definida pelo capitão ou pelo perfil da operação.

### 9.3 Comparação por custo do capitão

Cada execução registra backend, papel, tempo, retrabalho, tamanho do pacote entregue
ao capitão e veredito. A comparação útil não é “quantos tokens o trabalhador usou”,
mas “quanto trabalho confiável ele retirou do capitão por unidade de custo”. Uma
solução sem ponte vence se demonstrar essa vantagem; não ganha por elegância.

### 9.4 Backend `broker` — fase opcional e distante

Um broker local poderá futuramente invocar CLIs ou APIs externas e retirar a ponta
humana sem perder os agentes baratos. Ele não é prioridade enquanto a ponte estiver
funcionando e o custo humano for aceitável.

Gate econômico: considerar o broker apenas depois que o plano de controle, a
pré-revisão barata e a generalização estiverem validados em operações reais, e se o
proprietário identificar a ponte como gargalo dominante. A regra anterior de contar
ciclos, sozinha, é insuficiente: o ganho precisa superar o risco operacional e o
tempo de construção.

## 10. Evidência, baselines e retenção

### 10.1 Evidência durável

Só permanece no Git aquilo que participa de uma decisão futura:

- contagens e amostras pequenas;
- hash e proveniência do raw;
- comando, duração e resultado dos checks;
- diagnóstico ou decisão não reproduzível apenas pelo diff;
- manifesto de arquivos temporários usados.

### 10.2 Scratch

Raw volumoso, logs completos, saídas de compilação, DLLs e cópias de arquivos ficam
em `.scratch/`. A política padrão conserva:

- evidência da tarefa em execução;
- evidência de tarefa retornada ainda não aceita;
- a última evidência aceita quando necessária para comparação.

`om gc --dry-run` mostra o que é reproduzível e removível; a remoção efetiva exige
política configurada ou confirmação compatível com as regras do ambiente.

### 10.3 Baselines Git

O CLI referencia commits e extrai arquivos sob demanda para um diretório temporário.
Não cria diretórios `baseline-*` duráveis. Árvores sujas recebem um snapshot lógico
com hashes e patch, sem modificar a árvore. Quando um baseline não puder ser
reproduzido, essa limitação é explícita e o artefato necessário é promovido a
evidência durável.

### 10.4 Sondas reutilizáveis

Uma sonda NeoLua por operação ou, se genérica, um único harness versionado. Builds
ficam em cache/scratch. Tarefas apontam para a mesma ferramenta e guardam apenas os
casos e resultados pequenos. Três projetos copiados para a mesma operação deixam de
ser aceitáveis pelo `doctor` sem uma justificativa registrada.

Metas do replay:

- 31,31 MiB totais ao encerrar -> **menos de 2 MiB após `gc`**, preservado tudo
  que sustenta as decisões;
- pico de scratch durante a execução -> **medido separadamente**, sem misturá-lo
  com o estado canônico;
- três projetos NeoLua -> **um**;
- nove diretórios de baseline -> **zero**;
- raw duplicado durável -> **zero**;
- todo scratch mensurado e eliminável por política.

## 11. Interface mínima do CLI

Subcomandos previstos; cada um só entra quando um gate exigir:

```text
om op init        cria uma operação e sua configuração
om task new       cria o esqueleto curto de uma tarefa
om task publish   valida, sela e torna a tarefa ready
om task show      mostra a visão mínima para um papel
om task start     adquire lease e registra baseline
om check          executa e registra um check
om task finish    valida e gera resultado/evidência
om verify         registra uma verificação independente estruturada
om packet         gera a visão de decisão do capitão
om decide         capitão aceita, pede revisão ou registra bloqueio
om status         deriva fila, agentes, leases e próximos passos
om resume         gera a cápsula mínima de retomada por papel
om inbox          lista resultados que exigem decisão do capitão
om manager run    entrega o lote pronto no backend bridge
om doctor         valida toda a operação e suas invariantes
om metrics        compara métricas com a linha de base
om close          gera o fechamento canônico
om gc             audita ou aplica retenção de scratch
```

Isto é uma única ferramenta. Atalhos ou interfaces gráficas só serão considerados
depois de observar uso repetitivo que o justifique.

Implementação inicial recomendada: Python com biblioteca padrão, por já existir no
ambiente Windows (`py`), oferecer `tomllib`, subprocessos e testes sem
dependências. O núcleo não dependerá de PowerShell. Uma distribuição executável ou
reescrita só será cogitada se startup, instalação ou portabilidade forem medidos
como gargalo.

## 12. Métricas e orçamento de regressão

`om metrics` produzirá por operação:

- entrada e saída textual separadas por papel e backend;
- texto entregue e efetivamente lido pelo capitão, separado em intenções, correções,
  decisões e pacotes recebidos;
- bytes adicionais de diff/código/log deliberadamente abertos pelo capitão;
- ações explícitas de investigação do capitão: abrir diff, hunk, log ou arquivo e
  executar inspeção;
- custo barato empregado para cada unidade de trabalho retirada do capitão;
- arquivos e bytes duráveis por categoria;
- arquivos e bytes de scratch por categoria;
- palavras, linhas e bytes por tarefa e resultado;
- percentual de linhas estáticas repetidas;
- checks executados, duração e logs abertos na revisão;
- número de tarefas por lote;
- ciclos do backend, transportes humanos e mensagens;
- tempo entre `ready`, `running`, `returned` e `accepted`;
- violações prevenidas pelo validador;
- leituras de contexto fixo declaradas por papel;
- recall dos incidentes conhecidos no replay;
- achados não confirmados e revisões ampliadas desnecessárias em casos-controle;
- divergências entre escritor, verificadores e decisão final;
- custo do próprio CLI: comandos e arquivos adicionais.

Quando o ambiente não fornecer tokens por papel, palavras e bytes emitidos serão o
proxy reproduzível. O relatório não deve fingir precisão de tokens que não possui.

Orçamento para a operação completa `lua-translator-02`:

| Métrica | Base | Alvo v2 |
| --- | ---: | ---: |
| palavras do delta canônico da tarefa | 812 no pedido completo | <= 250 em média |
| bytes do delta canônico da tarefa | 6.211 no pedido completo | <= 2.000 em média |
| briefing resolvido do trabalhador | não separado | medir; pode crescer por qualidade |
| retorno bruto para verificadores | 901 palavras em média | medir; sem teto agressivo |
| pacote de decisão entregue ao capitão | retorno médio de 901 palavras | <= 200 em média |
| contexto fixo da skill para capitão | 2.080 palavras | <= 1.400 após dogfood |
| cápsula de retomada do capitão | handoff livre de até 102 linhas | <= 300 palavras |
| palavras de pedidos redigidas pelo capitão | >= 22.730 | <= 5.700 |
| palavras de retornos entregues ao capitão | >= 25.220 | <= 5.600 |
| achados bloqueantes históricos apresentados ao capitão | conjunto a congelar na Fase A | 100% |
| controles sem divergência escalados desnecessariamente | conjunto a congelar na Fase A | medir; recall isolado não aprova o gate |
| despachos + execuções manuais | 50 arquivos | 0 |
| transportes humanos, backend native | ~50 | 0, quando escolhido |
| transportes humanos, backend bridge | ~50 | métrica secundária; medir sem meta artificial |
| diretórios de baseline | 9 | 0 |
| projetos NeoLua na operação | 3 | 1 |
| arquivos de coordenação/estado | 109 | <= 70, salvo evidência excepcional |
| volume ao fim da operação | 31,31 MiB totais atuais | < 2 MiB após `gc` |
| estado/handoff inválido publicável | sim | não pelo CLI |

No orçamento acima, a redação de pedidos pelo capitão cai pelo menos 74,9% e a
entrada de retornos no capitão, pelo menos 77,8%. A soma desses dois limites
inferiores cai de 47.950 para 11.300 palavras: **76,4%**. Trabalhadores e revisores
podem consumir até três vezes mais para produzir essa economia, desde que o ganho e
a qualidade sejam medidos. O replay deve medir o realizado; estes números são
orçamento, não crédito antecipado.

O replay 13-a/13-b é um benchmark retrospectivo conhecido, não uma prova de
generalização. Antes de implementar as Fases C/D, a Fase A congela suas entradas, as
três divergências históricas, regra de pontuação e informação permitida a cada papel.
Agentes executores não recebem a solução final; o commit `80a0001` é oráculo somente
posterior. Sua economia usa como denominador exclusivamente a fatia histórica
13-a/13-b: texto escrito e recebido pelo capitão, bytes adicionais abertos e ações de
investigação recuperáveis. O orçamento 47.950 -> 11.300 continua pertencendo à
operação completa.

Regra de regressão: nenhuma alteração posterior pode piorar em mais de 10% o custo
do capitão, pedido, pacote de decisão ou artefatos sem registrar a causa e obter
aceite explícito. Aumento do custo barato não é regressão automática, mas deve trazer
ganho demonstrável de qualidade, cobertura ou economia do capitão.

## 13. Plano de implementação por gates

### Fase A — benchmark por papel e replay passivo

1. congelar as métricas acima em fixture e teste;
2. criar um importador somente leitura de `lua-translator-02`;
3. classificar conteúdo em protocolo repetido, decisão humana, evidência mecânica,
   log/raw e scratch reproduzível;
4. separar o que o capitão escreveu, recebeu e precisou abrir;
5. congelar um conjunto-ouro dos erros, divergências e decisões que o fluxo real
   encontrou, incluindo os casos que exigiram correção;
6. congelar casos-controle sem divergência relevante e medir achados não confirmados,
   revisões ampliadas desnecessárias e investigação adicional do capitão;
7. registrar uma baseline específica do par 13-a/13-b, partindo de `9e5cfeb`, com
   suas três divergências, fronteira de informação, pontuação e custos recuperáveis;
8. criar fixtures genéricas mínimas de tarefa de código, diagnóstico somente leitura
   e documentação/configuração;
9. gerar relatório de equivalência e custo por papel.

Gate A: os números do CLI precisam reproduzir as medições manuais com tolerância
explicada; incidentes e controles precisam estar enumerados; e 100% de recall não
pode, sozinho, aprovar qualidade. Nenhuma mudança da skill operacional nesta fase.

### Fase B — formato e validador, sem transporte

1. implementar `operation.toml`, front matter, efeitos `read-only`/`mutating`,
   eventos e máquina de estados local;
2. implementar `task publish`, `status`, `resume` e `doctor`;
3. converter, de forma automatizada, três recortes representativos: simples,
   correção/continuação e lote paralelo;
4. comparar tamanho e legibilidade com os originais.

Gate B: pedido convertido atinge o alvo, todas as invariantes conhecidas têm teste,
nenhum dado técnico necessário desaparece e o esquema não contém conceito exclusivo
do tradutor. Heartbeat e staleness de sessões permanecem fora desta fase.

### Fase C — preparação barata da tarefa

1. implementar intenções curtas e rascunhos de scout;
2. aceitar até três análises concorrentes somente leitura;
3. estruturar divergências sem pedir ao capitão que leia todos os rascunhos;
4. medir quanto da redação original do capitão foi substituída;
5. validar em ao menos um recorte simples e um de investigação ambígua.

Gate C: o capitão publica uma tarefa tecnicamente equivalente lendo e escrevendo no
máximo 25% das palavras da linha de base. O scout não pode ampliar escopo nem
transformar sua hipótese em decisão silenciosa.

### Fase D — captura, verificação e pacote de decisão

1. implementar leases, baseline, `check` e `finish`;
2. capturar automaticamente diff, caminhos, tempos e logs;
3. implementar verificadores independentes, achados estruturados e `packet`;
4. implementar política de scratch, manifests e `gc --dry-run`;
5. fazer replay de resultados simples, falhos, corrigidos e controversos;
6. comparar pacote novo com o conjunto-ouro da Fase A.

Gate D: pacote atinge o alvo, cobre de forma rastreável 100% dos IDs de achados,
apresenta 100% dos achados bloqueantes conhecidos e não usa escalada indiscriminada
para obter recall. O capitão consegue dar o mesmo veredito com no máximo 25% da
entrada textual original, sem perder acesso ao diff completo; bytes adicionais e
ações de investigação são publicados junto do resultado. Se logs brutos precisarem
ser abertos em todos os casos, ou controles limpos forem escalados sistematicamente,
a compactação falhou.

### Fase E — backend bridge com agentes baratos

1. implementar fila pronta, registro de sessão e `manager run`;
2. substituir despacho/execução por eventos;
3. permitir até três sessões externas com papéis e permissões distintos;
4. simular falha, parcial, retomada, lote paralelo e desacordo entre revisores;
5. implementar e testar heartbeat/staleness por backend;
6. medir custo dos trabalhadores, custo do capitão, ações humanas e payload.

Gate E: zero despacho/execução manual, nenhum enfraquecimento da fronteira do gerente
e redução do custo do capitão dentro do orçamento. A contagem de viagens é publicada
mesmo se não cair.

### Fase F — backend native comparável

1. definir um adaptador mínimo para as capacidades nativas do ambiente;
2. permitir ao capitão despachar e aguardar sem sessão intermediária;
3. replay de uma cadeia sequencial e um lote paralelo;
4. provar cancelamento, bloqueio e preservação do escritor exclusivo;
5. comparar Luna e agentes externos no mesmo esquema de qualidade e custo do capitão.

Gate F: nenhuma decisão técnica tomada pelo escalonador e dados suficientes para
escolher backend por papel. Zero transporte humano é benefício possível, não condição
para declarar a v2 útil.

### Fase G — dogfood geral e somente então mudança da skill

1. usar a v2 numa operação pequena real, mantendo fallback para o protocolo atual;
2. usar numa operação média com implementação e pelo menos uma revisão;
3. exigir que uma das duas operações seja de domínio, artefato ou toolchain
   claramente diferente do tradutor Lua;
4. colher métricas e fricções, sem acrescentar recursos por preferência estética;
5. alterar `SKILL.md` e referências apenas depois de o fluxo provar seu valor;
6. sincronizar instalações e publicar migração.

Gate G: metas de capitão e qualidade cumpridas em duas operações reais, incluindo a
operação não relacionada. O protocolo atual permanece como fallback até esse ponto.

### Fase H — decisão sobre broker

Aplicar o gate econômico da seção 9.4. Se a ponte não for o gargalo dominante,
registrar a decisão de não construir. Ausência do broker pode ser o resultado correto.

## 14. Ordem prática dos próximos passos

1. revisar este plano uma vez, com escopo fechado;
2. corrigir apenas falhas que afetem garantia, viabilidade ou métricas;
3. aprovar o candidato e criar uma branch de implementação;
4. executar somente a Fase A;
5. apresentar o relatório medido antes de iniciar a Fase B.

Não se deve implementar CLI, formatos e backend em um único salto. Cada fase precisa
mostrar o ganho que compra a complexidade seguinte.

## 15. Revisão externa sem loop infinito

O ChatGPT web pode ser útil como revisor adversarial do plano, não como coautor sem
limite. O pedido de revisão deve ser fechado:

1. verificar se cada mecanismo move uma métrica declarada;
2. procurar garantia perdida ou estado inválido ainda possível;
3. apontar onde uma solução mais simples entrega o mesmo ganho;
4. testar se o plano realmente reduz consumo do capitão, em vez de apenas deslocar
   ou esconder informação necessária;
5. procurar acoplamento disfarçado ao tradutor Lua;
6. verificar se os agentes baratos estão sendo usados até o limite útil antes de
   acrescentar trabalho ao capitão;
7. classificar cada achado como `bloqueante`, `importante` ou `opcional`;
8. não pedir expansão de escopo sem demonstrar qual meta falharia;
9. uma rodada de resposta do capitão encerra a revisão, salvo bloqueante novo e
   comprovado.

O capitão adjudica cada ponto contra a evidência da operação. Reintroduzir algo
removido deliberadamente exige mostrar uma garantia ou métrica perdida, não apenas
preferência de desenho.

## 16. Decisões firmes e decisões adiadas

### Firmes neste candidato

- uma única ferramenta pública;
- repositório separado para estado operacional;
- arquivos humanos pequenos + eventos estruturados;
- leitura direta de `events.jsonl` até desempenho justificar um índice;
- scratch ignorado e sujeito a retenção;
- estado sempre derivado;
- consumo e atenção do capitão são a principal função de custo;
- agentes baratos podem consumir mais para preparar e pré-revisar o trabalho;
- até três agentes baratos simultâneos, com uma única lease de escrita;
- ponte manual é backend econômico de primeira classe, não mero fallback;
- backend nativo compete por papel e pode coexistir com agentes externos;
- capitão sempre decide o aceite e sempre pode abrir o diff completo;
- validação em uma operação não relacionada ao tradutor é obrigatória;
- skill só muda depois do dogfood.

### Adiadas até medição

- nome definitivo do CLI e do repositório de operações;
- formato de empacotamento do Python;
- eventual índice SQLite regenerável;
- necessidade de daemon/broker;
- commit automático no repositório de operações;
- política padrão de worktree versus `in-place` por projeto;
- eventual renomeação da skill para refletir múltiplos transportes.

Essas decisões não impedem a Fase A e seriam prematuras antes do replay.

## 17. Resultado esperado

Ao final, o capitão deve escrever apenas o delta técnico e a decisão; o trabalhador,
apenas julgamento e achados que a máquina não pode inferir. Scouts pesquisam e
rascunham; escritores implementam; verificadores baratos organizam a evidência e
procuram falhas. Permissões recorrentes, estado, checks, diffs, tempos, locks,
métricas e retenção deixam de consumir redação humana.

O capitão recebe menos material, mas material mais denso: requisitos confrontados,
riscos, discordâncias e âncoras de código, com acesso irrestrito às fontes. A ponte
externa pode continuar existindo porque compra capacidade barata; delegação nativa
entra quando for economicamente ou tecnicamente melhor.

Esse é o ganho procurado: muito menos leitura, escrita e investigação do capitão,
compradas com trabalho barato e redundante, com mais — não menos — capacidade de
detectar erro e sem depender do domínio de uma tarefa específica.
