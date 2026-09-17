# Skill `orquestracao-manual`

Esta pasta contém a skill `orquestracao-manual` para agentes que coordenam sessões por meio de uma ponte humana e arquivos compartilhados.

## Instalação

Cada agente deve descobrir, de acordo com a sua própria harness, como instalar uma skill local. Ao instalar esta skill, copie somente:

- `SKILL.md`
- `references/`

Não copie os itens abaixo; eles pertencem ao repositório de manutenção ou ao material de apoio do projeto, não à skill:

- `.gitignore`
- `.git/`
- `manutencao/`
- `prompts/`
- `scripts/`
- `tests/`

Depois da instalação, a harness deve reconhecer a skill pelo nome `orquestracao-manual` e disponibilizá-la em uma nova sessão, conforme o mecanismo próprio de recarregamento ou descoberta de skills.

## Testes

As suítes pertencem ao repositório de manutenção. Rode Python com `py -B` (ou `PYTHONDONTWRITEBYTECODE=1`) para não deixar `__pycache__`.

Suíte portátil, sem o histórico da operação:

```powershell
py -B -m unittest discover -s tests
```

Ela não exercita as integrações históricas; esses testes são pulados sem a variável abaixo, e skips não contam como cobertura executada.

Suíte canônica, que mede a operação `lua-translator-02` de verdade:

```powershell
$env:OM_PHASE_A_HISTORY = "<pasta temp/tasks/lua-translator-02 da operação>"
py -B -m unittest discover -s tests
```
