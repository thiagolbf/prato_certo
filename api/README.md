# API — Controle de PF e Marmitas

Monolito modular em FastAPI (ADR-001). Comandos de desenvolvimento, testes e migrations estão
no `CLAUDE.md` da raiz do repositório.

## Comando técnico de ADMIN

A interface só cadastra Operadores. O **primeiro ADMIN**, um **ADMIN adicional** e a
**recuperação da senha do ADMIN** são feitos por um comando da API, por quem tem acesso ao
servidor (RN-34, RN-53). O comando usa o banco da `DATABASE_URL`, que precisa estar com as
migrations aplicadas.

A senha **nunca** é passada por argumento, porque ficaria no histórico do shell e na lista de
processos. O comando a pede duas vezes, sem mostrar o que é digitado. Ela precisa ter de 8
caracteres a 72 bytes (RN-60): sem acento, até 72 caracteres.

### Criar um ADMIN

Serve para o primeiro ADMIN e para os adicionais. O login é único no estabelecimento, sem
diferenciar maiúsculas (até 30 caracteres, sem espaços); o nome tem até 60.

```bash
# No terminal (em api/), contra o banco do .env da raiz
uv run python -m app.identidade.cli criar-admin --nome "Thiago" --login thiago

# No container da API (Docker Compose)
docker compose exec api python -m app.identidade.cli criar-admin --nome "Thiago" --login thiago
```

### Recuperar o acesso de um ADMIN

Troca a senha do ADMIN e libera a conta: zera as falhas de login e encerra o bloqueio em
curso, para ele entrar logo em seguida. Só vale para ADMIN: a senha de Operador é redefinida
pelo ADMIN, na interface (RN-52).

```bash
# No terminal (em api/)
uv run python -m app.identidade.cli redefinir-senha --login thiago

# No container da API
docker compose exec api python -m app.identidade.cli redefinir-senha --login thiago
```

No container, use `python` direto, sem `uv run`: a imagem só tem as dependências de produção,
e o `uv run` instalaria as de desenvolvimento dentro dela. Não use `docker compose exec -T`:
sem terminal, a senha aparece enquanto é digitada.
