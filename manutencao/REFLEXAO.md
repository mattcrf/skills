# Reflexão sobre a SKILL

Leia só quando o dono pedir uma sessão de manutenção. Nenhum papel da
orquestração carrega esta pasta.

## Autorização

- Vale só na sessão em que o dono pede.
- Permite criar e editar os arquivos de `manutencao/`.
- Editar `SKILL.md` ou `references/` exige um sim separado do dono para cada
  mudança.
- A pasta `manutencao/` não é espelhada. Uma mudança promovida à SKILL vale
  para as duas cópias: `C:\Users\mattc\Documents\orquestracao-manual` (fonte)
  e `C:\Users\mattc\.claude\skills\orquestracao-manual`. Confira as duas
  depois.

## Padrão

O resultado esperado é **não mudar**. Registrar um incidente não pede
proposta nenhuma. Ao consultar um agente, nunca pergunte "o que melhorar?":
pergunte se o incidente justifica mudar e aceite "não" como resposta.

## 1. Registrar

Uma linha em `incidentes.md`, só com fatos e referências. O dono informa
modelo e effort, escritos como `<modelo> (<effort>)`; se não informar,
escreva `desconhecido`.

## 2. Classificar

| Classe | Significa | Destino |
|---|---|---|
| E | O agente errou apesar de texto claro | Nota por modelo (memória do projeto) |
| P | O capitão escreveu mal, mas a regra já existe na SKILL | Nenhum, ou nota do capitão |
| T | Gosto técnico ou regra de projeto | `AGENTS.md` do projeto |
| L | Coordenação, transporte, permissão, estado ou formato que a SKILL não cobre | Candidato à SKILL |

Só a classe L segue adiante.

## 3. Portões (todos obrigatórios)

1. **Contrafactual:** o texto proposto, existindo, teria evitado o incidente
   com o mesmo agente?
2. **Generalidade:** vale para qualquer projeto e modelo, sem contradizer
   regras de projeto conhecidas?
3. **Já coberto:** cite o trecho da SKILL mais próximo. Se ele existe, a
   falha foi de aplicação, e mais texto não resolve.
4. **Recorrência:** ao menos 2 incidentes da mesma classe em operações ou
   modelos diferentes. Basta 1 se a segurança do protocolo quebrou (dois
   escritores, limite de trabalhadores excedido).
5. **Custo:** todo agente lê a SKILL em toda sessão. Prefira substituir ou
   apagar a acrescentar.

## Evidência

- Prefira o registro da sessão, que mostra o que o agente fez.
- Para perguntar a um agente, use só esta forma: "cite o arquivo e o trecho
  exato que levou à escolha X, com uma frase por citação dizendo como levou;
  se nenhum levou, diga isso". Confira cada citação no disco.
  - Uma citação que sustenta a escolha condena o texto citado.
  - Uma que não sustenta condena a leitura.
- Nunca use "explique sua decisão": a resposta é reconstruída depois e não
  serve de evidência.

## 4. Testar fora da SKILL

A mudança aprovada nos portões entra primeiro como cláusula em pedidos reais.
Só depois de funcionar é promovida à SKILL, com um sim do dono.

## 5. Rastrear e podar

- Cada linha promovida cita, em `incidentes.md`, o incidente que a motivou.
- Uma linha cujo motivo nunca mais se repetiu é candidata a remoção.
