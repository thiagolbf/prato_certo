# Review: T-12 — Aplicar o bloqueio por conta no login

> **Plano de referência:** `docs/plans/PLAN-001-controle-vendas-pf-marmitas.md`
> **PRD de referência:** `docs/prds/PRD-001-controle-vendas-pf-marmitas.md`
> **Arquitetura de referência:** `docs/architecture/proposta-arquitetural.md`
> **Reviewer:** Claude (skill `reviewer-leanwork` v1.0)
> **Data:** 2026-10-08
> **Round:** 2
> **Recomendação final:** ⚠️ Aprovado com ressalvas

---

## Sumário executivo

Os dois findings bloqueante e importante de concorrência do round 1 foram corrigidos e provados. O CA-38 agora grava com commit de verdade, troca o engine e confere o bloqueio no banco. Há um teste de concorrência para o `FOR UPDATE`, que falha sem o lock e passa com ele. A suíte tem 163 testes passando, o ruff está limpo e o `alembic check` não acusa diferença.

Continua pendente a confirmação do usuário sobre a conta desativada (R-03), e persiste a sugestão sobre o hash de referência (R-04). Não há bloqueante.

**Findings por severidade (round 2):**

| Severidade | Quantidade |
|------------|------------|
| Bloqueante | 0 |
| Importante | 1 |
| Sugestão   | 1 |
| **Total**  | **2** |

**Cobertura da tarefa:**

| Item | Esperado | Entregue | Status |
|------|----------|----------|--------|
| Regras implementadas (RN) | RN-37 (camada 1) | Completa no login | ✅ |
| Cenários validados (CA) | CA-24, CA-25, CA-38, CA-39 | os quatro, com prova de persistência para CA-38 | ✅ |
| Decisões base (ADR) | ADR-006, ADR-009 | respeitadas | ✅ |
| Critérios de aceite da tarefa | 3 itens | 3 atendidos | ✅ |
| Testes prometidos | 4 | 4, mais 1 de concorrência | ✅ |

---

## Contexto da implementação

### Stack detectada

- Backend: Python 3.12 + FastAPI, SQLAlchemy 2.0 async, Alembic, `uv`, `ruff`
- Banco: PostgreSQL 17
- Testes: pytest + pytest-asyncio + httpx, contra PostgreSQL real
- **Fonte:** `CLAUDE.md` da raiz e `docs/architecture/proposta-arquitetural.md`

### Escopo do diff

Diff contra `921c234` (árvore de trabalho, sem commit).

- **Declarado:** `api/app/identidade/servico_autenticacao.py`, `api/tests/identidade/test_bloqueio.py`
- **Registrado no plano durante a execução, com justificativa:** `api/app/identidade/repositorio.py`, `api/app/identidade/router.py`

---

## Findings detalhados

### 🔴 Bloqueantes

Nenhum.

### 🟡 Importantes

#### R-01 — Conta desativada não conta falha, e a decisão não está registrada (persiste do round 1 como R-03)

- **Eixo:** 3. Aderência ao spec
- **Referência cruzada:** RN-37; RN-38
- **Evidência:** `api/app/identidade/servico_autenticacao.py:57` (`if usuario.esta_bloqueado(agora) or not usuario.ativo:` retorna antes de `registrar_falha_login`)
- **Descrição:** a conta desativada recusa sem contar falha. A regra não trata esse caso. A escolha é razoável, mas está só no código.
- **Sugestão de correção:** o usuário confirma. Se confirmar, registrar na RN-37 do PRD e acrescentar um teste dedicado.

### 🟢 Sugestões

#### R-02 — Primeiro login com conta inexistente é mais lento (persiste do round 1 como R-04)

- **Eixo:** 5. Qualidade do código
- **Evidência:** `api/app/identidade/servico_autenticacao.py:22` (`_hash_sem_conta`)
- **Descrição:** a primeira recusa para login inexistente inclui a geração do hash de referência. Depois disso, os tempos ficam equivalentes.
- **Sugestão de correção:** gerar o hash no `lifespan` de `main.py`.

---

## Round anterior

Comparação com `REVIEW-T-12-2026-10-08.md` (round 1). A numeração recomeçou neste relatório.

| Item anterior | Status | Comentário |
|---------------|--------|------------|
| R-01 (round anterior) — CA-38 não provava o reinício | ✅ Resolvido | `test_CA_38_bloqueio_sobrevive_ao_reinicio` grava com commit, descarta o engine, cria outro e lê o bloqueio por ele. `tests/identidade/test_bloqueio.py:139`. |
| R-02 (round anterior) — sem teste de concorrência para o `FOR UPDATE` | ✅ Resolvido | `test_falhas_concorrentes_nao_se_perdem`, `tests/identidade/test_bloqueio.py:165`. Mutação conferida: sem `.with_for_update()` o teste falha em 3 de 3 execuções; com ele, passa. |
| R-03 (round anterior) — conta desativada sem registro | ⚠️ Persiste | Ver R-01 deste round. |
| R-04 (round anterior) — hash de referência sob demanda | ⚠️ Persiste | Ver R-02 deste round. |

---

## Verificação das correções

- **CA-38:** o teste confere a persistência com commit por requisição e engine recriado. O bloqueio está nas colunas da conta, não em memória de processo.
- **Concorrência:** duas tentativas erradas em paralelo, cada uma com sessão e commit próprios, resultam em `falhas_consecutivas == 2`. Sem o lock, o mesmo teste falha.
- **Tempo de resposta (CA-35):** conta inexistente, bloqueada, desativada e senha errada conferem a senha uma vez cada. Os tempos são equivalentes, salvo a primeira chamada (R-02).

---

## Notas ao processo (não-findings)

- **Ponto de validação humana:** o plano pede revisar a fase de autenticação inteira depois da T-12 (seção 9). Esta revisão de código não substitui essa validação.
- **Padrão emergente:** operações que precisam gravar falha e recusar precisam responder sem exceção. Vale registrar no `CLAUDE.md` com `/leanwork-context raiz`.

---

## Conclusão

A T-12 implementa a RN-37 na camada por conta, e as provas que faltavam foram adicionadas. O que resta é uma decisão do usuário (R-01) e uma otimização pequena (R-02).

**Recomendação: ⚠️ Aprovado com ressalvas.** A tarefa pode seguir para o commit, e a validação humana da fase de autenticação está pendente.

**Próximos passos sugeridos:**

- Confirmar a regra de conta desativada (R-01).
- Fazer a validação humana da fase de autenticação (T-08 a T-12) antes da T-13.
