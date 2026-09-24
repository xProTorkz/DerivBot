# CURRENT_STATE — DerivBot

Atualizado: 2026-09-24

```
PROJECT=DerivBot
REPOSITORY=xProTorkz/DerivBot
BRANCH=main
MASTER_ISSUE=#11
ACTIVE_ISSUE=#25
TASK_TYPE=INTELLIGENCE
BASELINE_SHA=e69cf585d0c5bcb91bb37cfbd00fbb17f54d610d
NEXT_AFTER_ACTIVE=#21
DEMO_ONLY=YES
REAL_ORDER_SENT=NO
```

## Execução ativa

#25 — Inteligência assertiva + recuperação 2x limitada pela meta da sessão.

Dependências/requisitos reutilizados:
`#13 → #17 → #14 → #16 → #18 → #19`

Não executar essas Issues em paralelo enquanto #25 estiver ativa.

## Arquivos prioritários da #25

```
src/core/inteligencia.py
src/core/motor.py
src/core/catalogador.py
src/config/config.py
src/main.py
tests/test_timing_regime_recovery.py
tests/test_micro_scalper.py
tests/test_concurrency_risk.py
tests/test_session_lifecycle.py
tests/test_issue23_confluencia.py
```

UI somente para o requisito explícito da barra/bolinhas amarelas:
```
templates/painel.html
static/scripts.js
static/style.css
```

## Skills

```
PRIMARY_SKILL=testes-validacao
SUPPORT_SKILL=pesquisa-projeto
CREATE_NEW_SKILL=NO
EXECUTION_PACKET=ISSUE_TOP
```

## Regra de contexto mínimo

Começar por `AGENTS.md` + este arquivo + EXECUTION PACKET no topo da Issue #25 + HEAD.
Abrir outros arquivos somente quando a implementação/teste exigir.
