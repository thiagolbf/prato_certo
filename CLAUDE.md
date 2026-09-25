# Controle de PF e Marmitas

<!-- leanwork-context:start -->

## Resumo

Sistema para o responsável por um restaurante registrar, no celular e em segundos, cada PF e marmita vendido,
e saber ao fim do dia quantos foram vendidos, quanto faturou e quanta proteína foi consumida — base para
planejar reposição. Não é sistema de pedidos, não emite nota e não processa pagamento. O clique de registro
no horário de pico é o caminho crítico; todo o resto acontece fora dele.

## Stack

- **Backend:** Python + FastAPI, SQLAlchemy 2.0 async (`asyncpg`, `AsyncSession`), Alembic
- **Frontend:** Next.js (App Router) + TypeScript
- **Banco:** PostgreSQL — mesma versão principal do Supabase, localmente em Docker Compose
- **Infra:** local em Docker Compose; publicação em Vercel (Web), Render (API, mesmo `Dockerfile`) e Supabase (só PostgreSQL) (ADR-008)
- **Testes:** <!-- TODO: framework de teste do backend e do frontend — não definido na proposta nem no repositório -->

## Comandos

<!-- TODO: nenhum comando detectado — o repositório ainda não tem scaffolding. Rodar /leanwork-context raiz de novo após o scaffolding. -->

## Convenções

- API é monolito modular: módulos `identidade`, `catalogo`, `vendas`, `relatorios`, cada um `router → service → repository`; módulo só fala com outro via service, nunca via repositório alheio (ADR-001)
- POO seletiva: regra de negócio vive em métodos das entidades de `identidade`, `catalogo` e `vendas`; service só orquestra. Regra de negócio no service é defeito (ADR-009)
- `relatorios` é procedural: agregação no SQL (`GROUP BY`/somatórios), nunca somando em Python (ADR-007, ADR-009)
- Routers são funções; autorização por perfil é dependência da rota, não da entidade (ADR-009)
- Comportamento direto nos modelos SQLAlchemy; schemas Pydantic separados, só como contrato HTTP. Sem `IRepository<T>` genérico, `UnitOfWork` próprio, mediator ou mapeador (ADR-009)
- Entre módulos trafega objeto de leitura imutável, nunca a entidade de outro módulo (ADR-009)
- Relacionamentos com `lazy="raise"`; carregar explicitamente (`selectinload`/`joinedload`) o que a entidade vai usar (ADR-009)
- Erros de regra são exceções de domínio, traduzidas para HTTP em um único handler (ADR-009)
- Repositórios recebem `estabelecimento_id` no construtor e filtram toda consulta por ele (ADR-003)
- Venda é append-only: sem `UPDATE` de valor nem `DELETE`; snapshot de preço/gramagem no registro; cancelamento lógico; chave de idempotência com índice único (ADR-004)
- Todo total exclui venda cancelada (`cancelada_em IS NULL`) (ADR-004)
- Instante sempre UTC gerado pelo servidor; dia operacional em `America/Sao_Paulo` calculado em um único lugar (ADR-005)
- Dinheiro sempre `Decimal`, nunca `float` (ADR-009)
- Nada bloqueante em `async def`: hash de senha via `asyncio.to_thread`; `httpx`, nunca `requests` (seção 6.2 da proposta)
- Sessão por cookie httpOnly; API servida same-origin via rewrite `/api/*` do Next.js; alteração de estado nunca por `GET` (ADR-006)
- Telas do app autenticado são client components, sem renderização no servidor (ADR-002)
- Toda configuração por variável de ambiente; API escuta em `$PORT`, expõe `/health` tocando o banco; nada gravado em disco; nenhum recurso proprietário de Vercel/Render/Supabase (ADR-008)
- Migrations sempre via Alembic, desde a primeira tabela; toda tabela de domínio tem `estabelecimento_id` (ADR-003)
- Testes de cenário do PRD carregam o ID do CA no nome (`CA_XX_descricao`), no formato que o framework exigir

## Restrições

- Backend Python/FastAPI e banco PostgreSQL — declarados pelo desenvolvedor
- Mobile first: uso principal no celular, registro em dois toques com retorno em menos de 1 s
- Sempre online — sem suporte offline
- Um desenvolvedor, sem operação dedicada
- Desenvolver e validar tudo localmente antes de publicar (ADR-008)
- Nunca SQLite, nem localmente

## Documentação

- **Arquitetura:** `docs/architecture/proposta-arquitetural.md` — ADRs inline na seção 5
- **PRDs:** `docs/prds/` — requisitos (RN-XX, CA-XX)
- **Planos:** `docs/plans/` — tarefas de execução (T-XX)
- **Reviews:** `docs/reviews/` — relatórios de review (R-XX)

## Como trabalhar neste projeto

Este projeto usa o pipeline SDD Leanwork. Antes de implementar qualquer feature:

1. Verifique se existe um plano em `docs/plans/PLAN-XXX-*.md`
2. Identifique a próxima tarefa pendente sem bloqueio: `Status: Pendente` e todas as tarefas de `Depende de:` com `Status: Concluído`
3. Leia a tarefa inteira, incluindo os campos `Implementa:`, `Valida:` e `Decisões base:`
4. Abra os artefatos referenciados:
   - Regras de negócio (`RN-XX`) → o PRD indicado no cabeçalho do plano
   - Critérios de aceite (`CA-XX`) → seção Gherkin do mesmo PRD
   - Decisões arquiteturais (`ADR-XX`) → `docs/architecture/`
5. Respeite os pontos de validação humana marcados no plano
6. Nomeie os testes conforme a convenção `CA_XX_*` para preservar rastreabilidade
7. Atualize o estado ao terminar: campo `Status:` da tarefa (`Pendente` → `Em andamento` → `Concluído`) e uma linha na tabela de Histórico de execução. O plano é a fonte de verdade do estado — tarefa concluída que continua `Pendente` fica invisível para quem retomar o trabalho
8. Execute **uma tarefa por vez** e peça review antes de seguir para a próxima

> Com o plugin Leanwork SDD instalado, `/leanwork-execute` faz os passos 1 a 8 e `/leanwork-review T-XX` faz a revisão. Sem o plugin, seguir os passos manualmente — eles não dependem de ferramenta.

<!-- leanwork-context:end -->

<!-- Conteúdo abaixo desta linha é mantido manualmente e não é alterado pela skill context-leanwork. -->
