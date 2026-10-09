# Review: T-13 — Expor o cadastro, a desativação e a reativação de operadores

> **Plano de referência:** `docs/plans/PLAN-001-controle-vendas-pf-marmitas.md`
> **PRD de referência:** `docs/prds/PRD-001-controle-vendas-pf-marmitas.md`
> **Arquitetura de referência:** `docs/architecture/proposta-arquitetural.md`
> **Reviewer:** Claude (skill `reviewer-leanwork` v1.0)
> **Data:** 2026-10-08
> **Round:** 2
> **Recomendação final:** ✅ Aprovado

---

## Sumário executivo

Os três itens do round 1 foram resolvidos e conferidos no código. Um ADMIN não consegue mais desativar a própria conta (`Usuario.exigir_desativavel_por`, `api/app/identidade/modelos.py:130-133`), e o router passa o id do ADMIN autenticado ao service. O `redefinir-senha` recusa conta desativada com mensagem clara, em vez de dizer que liberou (`api/app/identidade/cli.py:95-97`). Os três eventos de ADMIN (`usuario criado`, `usuario desativado`, `usuario reativado`) geram log com ids, sem nome nem login (`api/app/identidade/servico_usuarios.py:79, 92, 98`). Os três testes novos existem e passam.

Não há finding novo. A suíte tem 175 testes passando, o ruff está limpo e o `alembic check` não acusa diferença.

**Findings por severidade (round 2):**

| Severidade | Quantidade |
|------------|------------|
| Bloqueante | 0 |
| Importante | 0 |
| Sugestão   | 0 |
| **Total**  | **0** |

**Cobertura da tarefa:**

| Item | Esperado | Entregue | Status |
|------|----------|----------|--------|
| Regras implementadas (RN) | RN-34, RN-52, RN-60 | as três, com o caso de auto-desativação agora recusado | ✅ |
| Cenários validados (CA) | CA-65, CA-66 | os dois, por teste de HTTP | ✅ |
| Decisões base (ADR) | ADR-003, ADR-009 | respeitadas | ✅ |
| Critérios de aceite da tarefa | 3 itens | 3 atendidos | ✅ |
| Testes prometidos | 5 | 5, mais 5 complementares | ✅ |

---

## Contexto da implementação

### Stack detectada

- Backend: Python 3.12 + FastAPI, SQLAlchemy 2.0 async, Alembic, `uv`, `ruff`
- Banco: PostgreSQL 17
- **Fonte:** `CLAUDE.md` da raiz e `docs/architecture/proposta-arquitetural.md`

### Escopo do diff

Diff contra `2fab0aa` (árvore de trabalho, sem commit). O escopo é o mesmo do round 1: o declarado, mais `repositorio.py`, `main.py` e o router de usuários, todos justificados no plano antes da entrega.

---

## Findings detalhados

Nenhum.

---

## Round anterior

Comparação com `REVIEW-T-13-2026-10-08.md` (round 1). A numeração recomeçou neste relatório.

| Item anterior | Status | Comentário |
|---------------|--------|------------|
| R-01 (round anterior) — ADMIN podia desativar a própria conta; `redefinir-senha` não tratava conta desativada | ✅ Resolvido | `exigir_desativavel_por` recusa a auto-desativação com `RegraViolada` (422), testado por `test_admin_nao_desativa_a_propria_conta`. `redefinir-senha` recusa conta desativada, testado por `test_redefinir_senha_de_admin_desativado_e_recusado`. |
| R-02 (round anterior) — falta teste de 72 bytes no cadastro | ✅ Resolvido | `test_cadastro_recusa_senha_acima_de_72_bytes`. |
| R-03 (round anterior) — sem log de decisões de ADMIN | ✅ Resolvido | Logs `usuario criado`, `usuario desativado` e `usuario reativado`, com `usuario_id` e `por_id`. Nada de nome, login ou senha. |

---

## Notas ao processo (não-findings)

- **Regra de último ADMIN:** não foi implementada como regra separada. O ator de desativar é sempre um ADMIN ativo, porque `exige_admin` valida a sessão e a conta. Então qualquer desativação de outro ADMIN deixa o ator ativo, e a proibição de auto-desativação cobre o caso. A decisão está registrada aqui para o review futuro não exigir a regra de novo.
- **Duplicação pequena:** a montagem do `ServicoUsuarios` continua em dois lugares (router e `cli.py`). Não é finding; fica como nota para a T-14, se ela precisar do mesmo serviço.

---

## Conclusão

A T-13 entrega o que o plano pede, e os achados do round 1 foram tratados com teste. A tarefa está aprovada para o commit.

**Recomendação: ✅ Aprovado.**
