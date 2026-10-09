# Review: T-11 — Expor login, logout e sessão atual com cookie httpOnly

> **Plano de referência:** `docs/plans/PLAN-001-controle-vendas-pf-marmitas.md`
> **PRD de referência:** `docs/prds/PRD-001-controle-vendas-pf-marmitas.md`
> **Arquitetura de referência:** `docs/architecture/proposta-arquitetural.md`
> **Reviewer:** Claude (skill `reviewer-leanwork` v1.0)
> **Data:** 2026-10-08
> **Round:** 2
> **Recomendação final:** ⚠️ Aprovado com ressalvas

---

## Sumário executivo

A correção do round 1 foi aplicada e comprovada. `obter_sessao` agora é usado pelo alias `SessaoDaRequisicao`, com `Depends(obter_sessao, scope="function")`, em `estabelecimento.py`, `dependencias.py`, `router.py` e `main.py`. Com esse escopo, o commit roda ao fim da função da rota, antes do envio da resposta. Os dois testes de rota novos em `tests/core/test_db.py` (`test_commit_acontece_antes_do_envio_da_resposta` e `test_falha_de_commit_vira_erro_e_nao_sucesso`) falham com o escopo antigo e passam com o novo. A suíte tem 158 testes passando, o ruff está limpo e o `alembic check` não acusa diferença.

R-01 do round 1 está resolvido. Não há finding bloqueante. Persistem o desvio de processo sobre `tests/core/test_db.py` (agora Importante neste round) e as duas sugestões do round 1.

**Findings por severidade (round 2):**

| Severidade | Quantidade |
|------------|------------|
| Bloqueante | 0 |
| Importante | 1 |
| Sugestão   | 2 |
| **Total**  | **3** |

**Cobertura da tarefa:**

| Item | Esperado | Entregue | Status |
|------|----------|----------|--------|
| Regras implementadas (RN) | RN-38, RN-45, RN-54 | RN-38 e RN-45 completas; RN-54 com o commit antes do envio, provado por teste | ✅ |
| Cenários validados (CA) | CA-35, CA-42, CA-43, CA-56 | os quatro, por teste de HTTP | ✅ |
| Decisões base (ADR) | ADR-006, ADR-009 | respeitadas | ✅ |
| Critérios de aceite da tarefa | 3 itens | 3 atendidos | ✅ |
| Testes prometidos | 5 | 5, mais 4 complementares | ✅ |

---

## Contexto da implementação

### Stack detectada

- Backend: Python 3.12 + FastAPI, SQLAlchemy 2.0 async, Alembic, `uv`, `ruff`
- Banco: PostgreSQL 17
- Testes: pytest + pytest-asyncio + httpx (`ASGITransport`), contra PostgreSQL real
- **Fonte:** `CLAUDE.md` da raiz (seção Stack) e `docs/architecture/proposta-arquitetural.md`

### Padrões específicos aplicados (lidos do projeto)

- Routers são funções; service e repositório não importam FastAPI (CLAUDE.md, ADR-009)
- Alteração de estado só por POST (CLAUDE.md, ADR-006; RN-42)
- Logs sem senha, hash, cookie ou corpo de requisição (CLAUDE.md, RN-45)

### Escopo do diff

Diff contra `921c234` (árvore de trabalho, sem commit):

- **Arquivos modificados:** 6 (`api/app/core/db.py`, `api/app/core/estabelecimento.py`, `api/app/identidade/dependencias.py`, `api/app/identidade/router.py`, `api/app/main.py`, `docs/plans/PLAN-001-controle-vendas-pf-marmitas.md`)
- **Arquivos novos:** 5 (`api/app/identidade/router.py`, `api/app/identidade/schemas.py`, `api/app/identidade/servico_autenticacao.py`, `api/tests/core/test_db.py`, `api/tests/identidade/test_autenticacao.py`)
- **Commits:** 0

---

## Findings detalhados

### 🔴 Bloqueantes

Nenhum.

### 🟡 Importantes

#### R-01 — `tests/core/test_db.py` entrou no escopo da T-11 sem confirmação explícita (persiste do round 1 como R-02)

- **Eixo:** 1. Aderência ao plano
- **Referência cruzada:** seção T-11 do plano, "Camadas/arquivos afetados"; regra de execução (arquivo fora da lista exige justificativa explícita antes de ser tocado)
- **Evidência:** `api/tests/core/test_db.py` (novo); `docs/plans/PLAN-001-controle-vendas-pf-marmitas.md`, linha de `api/tests/core/test_db.py` dentro de T-11, acrescentada durante a execução
- **Descrição:** a aprovação do usuário cobriu `core/db.py`. O arquivo de teste foi incluído no plano depois do início da tarefa, e a pergunta sobre ele não foi feita. Nesta rodada, o usuário pediu que eu "fizesse o que for melhor", o que cobre a decisão de manter o teste. Ainda assim, a inclusão não foi confirmada como escopo da T-11, e o plano foi alterado para acompanhar o código.
- **Por que é Importante:** não afeta o comportamento. É um desvio de processo, e o plano precisa refletir o que foi decidido.
- **Sugestão de correção:** registrar no histórico da T-11 que o teste foi mantido por decisão do usuário, ou movê-lo para um item próprio do plano, se o usuário preferir.

### 🟢 Sugestões

#### R-02 — Primeiro login com conta inexistente é mais lento: hash de referência é gerado sob demanda (persiste do round 1 como R-03)

- **Eixo:** 5. Qualidade do código (tempo de resposta, CA-35)
- **Referência cruzada:** CA-35
- **Evidência:** `api/app/identidade/servico_autenticacao.py` (`_hash_sem_conta` gera o hash na primeira chamada)
- **Descrição:** a primeira requisição com login inexistente demora mais por causa da geração do hash de referência. A diferença acontece uma vez por processo.
- **Sugestão de correção:** gerar o hash de referência no `lifespan` de `main.py`, ou aceitar e registrar.

#### R-03 — Limites de login diferentes entre a API e o cadastro (persiste do round 1 como R-04)

- **Eixo:** 5. Qualidade do código
- **Referência cruzada:** RN-60
- **Evidência:** `api/app/identidade/schemas.py` (`LoginEntrada.login`, até 60 caracteres); `api/app/identidade/cli.py` (`Login`, até 30)
- **Descrição:** cadastro aceita até 30 caracteres, login aceita até 60. Não causa erro, porque um login mais longo que o cadastrado simplesmente não existe.
- **Sugestão de correção:** unificar quando a T-13 mover os limites para `schemas.py` do módulo.

---

## Round anterior

Comparação com `REVIEW-T-11-2026-10-08.md` (round 1). A numeração recomeçou neste relatório: os `R-XX` da coluna abaixo são do round 1.

| Item anterior | Status | Comentário |
|---------------|--------|------------|
| R-01 (round anterior) — `obter_sessao` commitava depois do envio da resposta | ✅ Resolvido | Escopo `function` no alias `SessaoDaRequisicao`. Dois testes de rota novos falham com o escopo antigo e passam com o novo. |
| R-02 (round anterior) — `tests/core/test_db.py` fora do escopo aprovado | ⚠️ Persiste | Ver R-01 deste round. Severidade mantida como Importante. |
| R-03 (round anterior) — hash de referência gerado sob demanda | ⚠️ Persiste | Ver R-02 deste round. |
| R-04 (round anterior) — limites de login diferentes | ⚠️ Persiste | Ver R-03 deste round. |

---

## Verificação da correção (R-01 do round anterior)

- **Ordem comprovada:** com o escopo padrão, a resposta sai antes do commit. Com `scope="function"`, o commit sai antes da resposta (reprodução em `scratchpad/ordem.py` e teste `test_commit_acontece_antes_do_envio_da_resposta`).
- **Falha de commit:** com `scope="function"`, uma violação de chave estrangeira no commit vira 500 com a mensagem genérica, e não 2xx (`test_falha_de_commit_vira_erro_e_nao_sucesso`).
- **Abrangência:** todas as dependências que usam a sessão passam pelo alias, então a ordem vale para login, logout, `/me`, `/health` e as rotas futuras que usarem `SessaoDaRequisicao`.
- **Limite:** um endpoint que declare `Depends(obter_sessao)` direto, sem o alias, volta ao escopo padrão. O alias existe para evitar isso. Vale uma verificação no review das próximas tarefas.

---

## Notas ao processo (não-findings)

- **Status no plano:** a T-11 está `Concluído`, e este round não tem bloqueante. O histórico da T-11 ainda diz "Commit pendente" e não cita a correção de R-01. Atualizar a linha do histórico quando o commit acontecer.
- **Padrão emergente:** toda dependência com `yield` que escreve no banco precisa de `scope="function"`. Vale registrar no `CLAUDE.md` com `/leanwork-context raiz`.

---

## Conclusão

A T-11 atende os critérios de aceite, e o defeito do round 1 foi corrigido com prova de regressão. O que resta é de processo (R-01) e de qualidade, sem efeito no comportamento.

**Recomendação: ⚠️ Aprovado com ressalvas.** A tarefa pode seguir para o commit.

**Próximos passos sugeridos:**

- Registrar no histórico do plano a correção de R-01 e o status deste round.
- Decidir se `tests/core/test_db.py` fica na T-11 ou vira item próprio (R-01).
- Considerar R-02 e R-03 nas tarefas T-12 e T-13.
