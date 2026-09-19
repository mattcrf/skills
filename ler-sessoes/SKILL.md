---
name: ler-sessoes
description: Ler sessoes locais de agentes e resumir cada evento em uma linha de texto puro para outro agente analisar.
disable-model-invocation: true
---

# Ler sessões

Resume sessões de agentes a partir dos logs locais, sem abrir o log: texto puro,
um evento por linha, pensado para gastar poucos tokens.

O CLI fica em `scripts/sessoes.py`; rode com `py -B` e aponte os logs com
`--raiz` quando não forem o padrão:

```text
sessoes.py lista [--ferramenta NOME] [--desde AAAA-MM-DD]
sessoes.py linha <id> [--tipo cmd,edit] [--falhas] [--grep REGEX] [--de N] [--ate N] [--largura 160]
sessoes.py mostra <id> <n> [--max-bytes 4000]
```

`<id>` aceita prefixo único; prefixo ambíguo lista os candidatos e falha.
Durações: `43s`, `12m05s`, `1h18m`.

## lista

Uma linha por sessão de todas as ferramentas, ou só de `--ferramenta`, da mais
recente para a mais antiga:

- `id`: começo do identificador, serve para `linha` e `mostra`.
- `ferramenta`: leitor que produziu a sessão.
- `modelo/esforço`: modelo e esforço do primeiro turno.
- `início`: horário local.
- `duração`: do início ao fim do último turno; inclui pausas entre turnos; `-`
  se desconhecida.
- `tokens`: entrada/saída acumuladas.
- `término`: `fim` quando o último turno terminou; senão `sem-fim`.
- `pai`: sessão que criou esta.
- `nome`: caminho do subagente.

## linha

Um cabeçalho (`# id ferramenta modelo/esforço início duração término nome
cwd=...`) e, depois, `n Mm duração !exit tipo texto`:

- `n`: número estável do evento, usado em `mostra` e em `--de`/`--ate`.
- `Mm`: minuto do evento desde o início da sessão (`15m`).
- `duração`: do evento, só a partir de 1 s.
- `!n`: exit diferente de zero.
- `texto`: uma linha, cortada em `--largura` com `…`, com caminhos dentro do
  `cwd` do cabeçalho relativos. Em `edit`, cada arquivo leva `+` criado, `~`
  alterado ou `-` removido.
- `--tipo` filtra tipos; `--falhas` mostra exit diferente de zero e erro de
  ferramenta; `--grep` procura no conteúdo completo, não no texto cortado.

## Tipos

- `user`: mensagem do usuário.
- `msg`: mensagem do agente.
- `think`: resumo de raciocínio.
- `cmd`: comando executado.
- `edit`: arquivo criado, alterado ou removido.
- `tool`: chamada de ferramenta externa.
- `agent`: subagente iniciado, concluído ou chamada de colaboração.
- `compact`: compactação de contexto.
- `?`: tipo desconhecido; o texto traz o nome.

## mostra

O evento inteiro: comando, cwd, exit, duração e saída. Acima de `--max-bytes`,
guarda o começo e o fim e diz quantos bytes cortou do meio.
