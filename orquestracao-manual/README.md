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

Depois da instalação, a harness deve reconhecer a skill pelo nome `orquestracao-manual` e disponibilizá-la em uma nova sessão, conforme o mecanismo próprio de recarregamento ou descoberta de skills.
