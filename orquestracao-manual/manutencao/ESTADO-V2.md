# Estado operacional da v2

Este arquivo preserva decisões atuais de produto que não devem depender da
memória de uma sessão. `PLANO-V2.md` continua sendo histórico e horizonte; esta é
a fotografia do que pode ser usado agora.

## Entrega operacional atual

- A fonte de verdade é este repositório; instalações em `.codex` e `.claude` são
  cópias sincronizadas de `SKILL.md`, `references/` e `scripts/`.
- O CLI público prepara operações: `op init`, `task new`, `task publish`,
  `bridge dispatch`, `status`, `resume` e `doctor`.
- O CLI não executa agentes nem implementa ainda start/finish/check/packet/decide,
  leases, inbox, retenção ou `manager run`.
- A ponte usa um despacho gerado. O gerente encadeia agentes com ferramentas
  nativas e escreve um índice; trabalhadores escrevem retornos; o capitão julga
  retornos, diff e evidências.
- O caminho rotineiro de implementação tem exatamente um escritor seguido por um
  verificador independente. Scout só entra quando uma dúvida factual impede o
  pedido. Não há curador.
- Uma única tarefa mutante pode estar ativa. Até três agentes baratos são
  capacidade máxima, não objetivo.
- Metas de 2.000 bytes e 250 palavras são diagnóstico após completude. Publicação
  acima da meta é permitida e marcada `budget=over`; truncamento e ciclos de
  compressão são defeitos.
- Despacho contém dados; comportamento do gerente pertence à referência do papel.
  Pedidos contêm delta técnico; protocolo e regras locais permanecem nas fontes.
- O gerente não cria tarefas, não lê conteúdo técnico e não arbitra. Trabalhadores
  não delegam. O capitão é o único aceitador técnico.
- Um revisor externo pode auditar a operação e o desempenho dos papéis, mas não é
  uma sessão obrigatória da cadeia nem substitui o capitão.

## Decisões deliberadamente adiadas

- automação da execução e de leases;
- captura automática de checks/diff e pacote de decisão;
- backend nativo e broker;
- coleta completa de métricas e `gc`;
- repositório central definitivo de operações.

Nenhuma documentação pública pode anunciar essas funções antes de existirem e
passarem por dogfood real.

## Próxima validação

Uma sessão Claude sem o contexto histórico deve, usando somente a skill instalada:

1. atuar como capitão e preparar uma operação pequena;
2. criar e publicar escritor + verificador;
3. gerar um despacho mínimo sem regras duplicadas;
4. permitir que um gerente encadeie as duas sessões;
5. produzir retornos que um revisor externo consiga confrontar com pedidos, diff e
   evidências.

Falha nessa jornada é defeito da superfície pública atual, não convite para mais
papéis ou texto defensivo.
