# CURRENT_STATE — DerivBot

Atualizado: 2026-09-24

```
PROJECT=DerivBot
REPOSITORY=xProTorkz/DerivBot
BRANCH=main
MASTER_ISSUE=#11
ACTIVE_ISSUE=#25 (DONE) -> NEXT: #21
TASK_TYPE=INTELLIGENCE
BASELINE_SHA=f9cc3c713acaebf4c022e30441d141c198f1c274
NEXT_AFTER_ACTIVE=#21
DEMO_ONLY=YES
REAL_ORDER_SENT=NO
```

## Execução concluída

#25 — Inteligência assertiva + recuperação 2x limitada pela meta da sessão.
Status: DONE (Validado com 105/105 testes, commit f9cc3c7 sincronizado com origin/main).

Próxima tarefa autorizada na fila: #21 (E2E/soak DEMO).

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
