# Skill `ler-sessoes`

Fonte versionada da skill que resume sessões locais de agentes para outro agente
analisar.

## Instalação

Copie para as duas instalações, `~/.claude/skills/ler-sessoes` e
`~/.codex/skills/ler-sessoes`:

- `SKILL.md`
- `scripts/`

Não copie `.git/`, `tests/`, `temp/` ou caches Python. A skill instalada precisa
conservar a mesma estrutura relativa, pois `SKILL.md` aponta para os scripts e os
módulos se importam entre irmãos em `scripts/`.

Depois de copiar, abra uma sessão nova ou use o mecanismo de recarga da harness.
Confirme a instalação sem ler o código:

```powershell
py -B "<skill-instalada>\scripts\sessoes.py" --help
py -B "<skill-instalada>\scripts\sessoes.py" lista --help
```

Sem `--raiz`, o CLI lê os logs do Codex em `~/.codex/sessions`. A sessão de
origem não importa: qualquer pasta com a mesma árvore serve.

## Testes da fonte

Rode sem criar `__pycache__`:

```powershell
py -B -m unittest discover -s tests
```

As fixtures são sintéticas e escritas à mão. Nunca copie um log real para
`tests/`.
