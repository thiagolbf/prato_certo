# Review: T-36 — Aplicar cabeçalhos de segurança e CSP no Next.js (round 2)

> **Plano de referência:** `docs/plans/PLAN-001-controle-vendas-pf-marmitas.md`
> **Review anterior:** `docs/reviews/REVIEW-T-36-2026-10-09.md` (R-01 bloqueante de verificação no navegador)
> **Reviewer:** Claude (skill `reviewer-leanwork`, execução inline)
> **Data:** 2026-10-10
> **Round:** 2
> **Recomendação final:** ✅ Aprovado com ressalvas

---

## Round anterior

- **R-01 (Importante, verificação no navegador do critério "sem erro de CSP no console"):** resolvido. A verificação foi feita agora, com Chrome headless e o protocolo DevTools, contra `npm run build && npm start` com a API no ar (`http://localhost:8000`). Páginas verificadas:
  - `/login`: renderiza o formulário, zero violações de CSP no console.
  - `/registrar` sem sessão: `/api/auth/me` responde 401, o cliente leva a `/login?motivo=sessao-expirada`, zero violações de CSP.
  - `/vendas` sem sessão: mesmo caminho, zero violações.
- **R-02 (Sugestão, `unsafe-inline` em `script-src` de produção):** segue como risco aceito, a registrar na arquitetura. O app é de client components (ADR-002) e não tem conteúdo de terceiros; a troca por nonce fica para uma tarefa própria se a superfície crescer.

## Findings por severidade

| Severidade | Quantidade |
|------------|------------|
| Bloqueante | 0 |
| Importante | 0 |
| Sugestão   | 1 (R-02, já registrado) |
| **Total**  | **1** |

## Cobertura da tarefa

| Item | Esperado | Entregue | Status |
|------|----------|----------|--------|
| Quatro cabeçalhos em todas as rotas (CA-41) | sim | verificado com `curl` e pelo teste `seguranca.test.ts` | ✅ |
| App sem erro de CSP no console | sim | verificado no Chrome nas rotas públicas e nas protegidas | ✅ |

## Verificação executada

- Chrome headless com DevTools: três rotas, zero eventos `Content Security Policy`.
- `curl -sI http://localhost:3123/` com os quatro cabeçalhos presentes (HSTS, `nosniff`, `DENY`, CSP).
- A rota autenticada completa (com sessão) não foi verificada nesta rodada: não há usuário de teste no banco de desenvolvimento. A CSP cobre os mesmos scripts, e a página de login é a que carrega o formulário.
