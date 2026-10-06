# Web — Controle de PF e Marmitas

Next.js (App Router) + TypeScript. Node 24 (`.nvmrc`).

```bash
cp .env.example .env.local   # API_URL: para onde /api/* é reescrito (ADR-006)
npm install
npm run dev                  # http://localhost:3000
npm test                     # Vitest + Testing Library
npm run lint
npm run typecheck
```

A API precisa estar no ar no endereço de `API_URL` (Docker Compose na raiz do repositório).
