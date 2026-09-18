# CLI `om`

Esta é a interface pública da versão instalada. Não leia o código para descobrir
comandos e não use comandos mencionados apenas no plano de manutenção.

## Invocação

Resolva `<skill>` como a pasta que contém o `SKILL.md` lido nesta sessão. No
Windows:

```powershell
py -B "<skill>\scripts\om.py" <comando>
```

Se a harness fornece outro executável Python, substitua apenas `py -B`. Use
`--help` no comando real quando precisar confirmar argumentos.

## Preparação completa de um segmento

Crie a operação na raiz padrão. `--id` também nomeia sua pasta:

```powershell
py -B "<skill>\scripts\om.py" op init `
  --id "<id-da-operação>" --project-root "<projeto>"
```

No Windows, a raiz padrão é
`%USERPROFILE%\Documents\skills\temp\ops`; portanto o comando acima cria
`%USERPROFILE%\Documents\skills\temp\ops\<id-da-operação>`. A variável
`ORQUESTRACAO_MANUAL_OPS_ROOT`, quando definida com caminho absoluto, muda essa
raiz. Use `--operation "<caminho absoluto>"` somente quando o usuário escolher
outro local. A saída de `op init` informa o caminho absoluto canônico; reutilize-o
nos comandos seguintes, sem reconstruí-lo.

Crie o escritor e o verificador. O segundo depende do primeiro:

```powershell
py -B "<skill>\scripts\om.py" task new `
  --operation "<operação>" --id "01-a" --kind writer --title "<entrega>"

py -B "<skill>\scripts\om.py" task new `
  --operation "<operação>" --id "01-b" --kind verifier `
  --depends "01-a" --title "Verificar <entrega>"
```

Os comandos imprimem os caminhos dos rascunhos em `.scratch/drafts/`. Edite-os,
substitua todos os `TODO:` e então publique:

```powershell
py -B "<skill>\scripts\om.py" task publish `
  --operation "<operação>" --task "<rascunho>"
```

Publicar copia o pedido para `tasks/`, cria `evidence/<ID>/`, grava seu hash no
log e impede alterações silenciosas. A saída informa bytes, palavras e
`budget=within|over`. `over` não é erro e nunca autoriza truncamento.

Valide e gere o despacho:

```powershell
py -B "<skill>\scripts\om.py" doctor --operation "<operação>"

py -B "<skill>\scripts\om.py" bridge dispatch `
  --operation "<operação>" --slots 2
```

O último comando cria `dispatch.md` e imprime a linha `manager:` pronta para a
ponte. O arquivo contém somente dados operacionais e os caminhos absolutos do
protocolo; não o complemente com explicações.

Para outro segmento da mesma operação, publique IDs novos e gere outro arquivo:

```powershell
py -B "<skill>\scripts\om.py" bridge dispatch `
  --operation "<operação>" --tasks "02-a" "02-b" `
  --out "<operação>\dispatch-02.md" --slots 2
```

## Consultas

```powershell
py -B "<skill>\scripts\om.py" status --operation "<operação>" --brief
py -B "<skill>\scripts\om.py" resume --operation "<operação>" --role captain
py -B "<skill>\scripts\om.py" doctor --operation "<operação>"
```

Nesta versão, `status` e `resume` descrevem somente a publicação e as dependências
do segmento; `execution*.md` e `results/` registram a execução real. O capitão lê
esses arquivos na volta.

## Limite da versão

Estão implementados para operação: `op init`, `task new`, `task publish`,
`bridge dispatch`, `status`, `resume` e `doctor`. Os subcomandos `benchmark` são
de manutenção da skill, não do fluxo cotidiano.

Não existem ainda `task start`, `task finish`, `check`, `verify`, `packet`,
`decide`, `inbox`, `manager run`, `close` ou `gc`. Não os invoque nem afirme que
leases, execução, checks, aceite ou retenção são automatizados. Gerente,
trabalhadores e capitão continuam responsáveis por essas etapas conforme suas
referências.
