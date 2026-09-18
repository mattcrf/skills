# Skill `orquestracao-manual`

Fonte versionada da skill de coordenação por ponte humana.

## Instalação

Copie para as duas instalações, `~/.claude/skills/orquestracao-manual` e
`~/.codex/skills/orquestracao-manual`:

- `SKILL.md`
- `references/`
- `scripts/`

Não copie `.git/`, `manutencao/`, `tests/`, `temp/` ou caches Python. A skill
instalada precisa conservar a mesma estrutura relativa, pois `SKILL.md` aponta
para as referências e o CLI importa módulos irmãos em `scripts/`.

Depois de copiar, abra uma sessão nova ou use o mecanismo de recarga da harness.
Confirme a instalação sem ler o código:

```powershell
py -B "<skill-instalada>\scripts\om.py" --help
py -B "<skill-instalada>\scripts\om.py" op init --help
py -B "<skill-instalada>\scripts\om.py" bridge dispatch --help
```

## Testes da fonte

Rode sem criar `__pycache__`:

```powershell
py -B -m unittest discover -s tests
```

A suíte canônica histórica é opcional e exige:

```powershell
$env:OM_PHASE_A_HISTORY = "<pasta temp/tasks/lua-translator-02>"
py -B -m unittest discover -s tests
```
