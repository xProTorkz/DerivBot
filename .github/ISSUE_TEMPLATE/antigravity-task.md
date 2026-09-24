---
name: Antigravity Task
about: Tarefa pronta, mínima e executável pelo Antigravity
title: "[P0/P1/P2] "
labels: ""
assignees: ""
---

# EXECUTION PACKET

```
PROJECT=DerivBot
REPOSITORY=xProTorkz/DerivBot
BRANCH=main
MASTER_ISSUE=#11
TASK_TYPE=
BASELINE_SHA=
SKILL_PRIMARY=
SKILL_SUPPORT=
DEMO_ONLY=YES
REAL_ORDER_SENT=NO
```

## Roteamento obrigatório

Use `AGENTS.md` para mapear `TASK_TYPE` → Skill e arquivos iniciais.

Tipos canônicos:
```
INTELLIGENCE
RISK
UI
RUNTIME
AUTH
AUDIT
STATUS
```

A Issue deve sair pronta com Skill principal/suporte preenchidas. Não delegar ao Antigravity a descoberta ampla do escopo.

## Objetivo único

<!-- Uma frase: resultado que deve existir quando a tarefa terminar. -->

## Contexto mínimo

```
READ_FIRST=AGENTS.md,.agents/context/CURRENT_STATE.md,this issue
DO_NOT_SCAN_FULL_REPO=YES
```

## Estado inicial comprovado

<!-- HEAD, comportamento atual, evidência/erro observado. -->

## Escopo permitido

### Arquivos primários
```
path/arquivo.py
```

### Arquivos permitidos somente se necessários
```
path/outro.py
```

## Fora de escopo

- sem refactor oportunista;
- sem arquitetura paralela;
- sem novas Skills;
- sem credenciais;
- sem REAL;
- sem executar próxima Issue.

## Implementação obrigatória

<!-- Passos técnicos objetivos, sem investigação ampla quando já conhecida. -->

## Testes focados

```
comando / arquivo de teste existente
```

## Regressão

```
testes relacionados que não podem quebrar
```

## Critérios de aceite

```
CRITERIO_1=PASS
CRITERIO_2=PASS
TESTS=PASS
REAL_ORDER_SENT=NO
```

## Entrega

```
BASELINE_SHA=
FINAL_SHA=
FILES_CHANGED=
FOCUSED_TESTS=
REGRESSION_TESTS=
ACCEPTANCE=
COMMIT=
PUSH=
MASTER_UPDATED=
```
