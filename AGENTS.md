# AGENTS.md — DerivBot

Este arquivo é o contrato mínimo de execução para agentes automatizados neste repositório.

## Identidade canônica

- Projeto: DerivBot
- Repositório: `xProTorkz/DerivBot`
- Branch operacional: `main`
- Issue master: `#11`
- Fonte de verdade: GitHub + código atual
- Ambiente de ordens autorizado nesta fase: DEMO
- `REAL_ORDER_SENT=NO`

## Ordem obrigatória para qualquer tarefa

1. Ler `.agents/context/CURRENT_STATE.md`.
2. Ler somente a Issue ativa indicada em `ACTIVE_ISSUE`.
3. Confirmar HEAD atual.
4. Carregar somente os arquivos listados na Issue / pacote executivo.
5. Aplicar a menor alteração suficiente.
6. Executar primeiro testes focados, depois regressão necessária.
7. Revisar diff.
8. Commit + push somente após PASS.
9. Atualizar a Issue ativa e a #11 com evidências.

Não varrer o repositório inteiro se o pacote executivo já indicar os arquivos.

## Skills globais

As Skills são globais e não devem ser duplicadas dentro deste repositório.

Roteamento canônico:
- `pesquisa-projeto`: recuperar contexto, decisões, baseline, Issue, arquivos e dependências estritamente necessárias.
- `testes-validacao`: planejar baseline, testes focados, regressão, comparação antes/depois e evidências de aceite.

Para tarefas de código, usar ambas sob demanda. Não criar Skill nova sem necessidade comprovada.

## Mapa mínimo do código

### Inteligência / sinais / timing / regime
- `src/core/inteligencia.py`
- `src/core/catalogador.py`
- `src/config/config.py`
- testes primários: `tests/test_timing_regime_recovery.py`, `tests/test_micro_scalper.py`

### Motor / contratos / settlement / sessão
- `src/core/motor.py`
- `src/core/deriv_api.py`
- `src/main.py`
- testes primários: `tests/test_session_lifecycle.py`, `tests/test_issue23_confluencia.py`

### Risco / concorrência
- reutilizar a implementação de risco existente localizada pelo código atual;
- `src/core/motor.py`
- `src/config/config.py`
- teste primário: `tests/test_concurrency_risk.py`

### UI / painel
- `templates/painel.html`
- `static/scripts.js`
- `static/style.css`
- `src/main.py` somente para schema/status necessário à UI.

### Runtime / autenticação
- `src/main.py`
- `src/core/motor.py`
- `src/core/deriv_api.py`
- testes: `tests/test_runtime_and_scanner.py`, `tests/test_deriv_auth.py`

## Restrições

- Não alterar arquivos fora do escopo sem causa direta.
- Não fazer refactor oportunista.
- Não criar arquitetura paralela.
- Não duplicar mecanismo existente.
- Não inserir credenciais.
- Não habilitar ordens REAL.
- Não criar arquivos de teste descartáveis quando os testes atuais puderem ser estendidos.
- Não executar Issues seguintes automaticamente.

## Critério de conclusão

Uma tarefa só é DONE quando houver:
- baseline identificado;
- diff revisado;
- testes focados PASS;
- regressão aplicável PASS;
- critérios de aceite comprovados;
- commit/push confirmados;
- Issue ativa e master sincronizadas.
