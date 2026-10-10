import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProvedorSessao, type Perfil } from "@/lib/sessao";

import { AppShell } from "./AppShell";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/registrar",
  useRouter: () => ({ replace }),
}));

afterEach(() => {
  vi.restoreAllMocks();
  replace.mockClear();
});

function renderizar(perfil: Perfil) {
  return render(
    <ProvedorSessao valor={{ nome: "Ana", perfil, diaOperacional: "2026-10-10" }}>
      <AppShell>
        <p>Conteúdo</p>
      </AppShell>
    </ProvedorSessao>,
  );
}

test("AppShell mostra a navegação do Operador", () => {
  renderizar("OPERADOR");

  expect(screen.getByRole("link", { name: "Registrar" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Minhas vendas" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Vendas" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Mais" })).not.toBeInTheDocument();
});

test("AppShell mostra a navegação do ADMIN e o Mais", () => {
  renderizar("ADMIN");

  expect(screen.getByRole("link", { name: "Registrar" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Vendas" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Fechamento" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cardápio" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Mais" }));

  expect(screen.getByRole("link", { name: "Proteínas" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Usuários" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Trocar minha senha" })).toBeInTheDocument();
});

test("Sair chama POST /api/auth/logout", async () => {
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(null, { status: 204 }));
  renderizar("OPERADOR");

  fireEvent.click(screen.getByRole("button", { name: "Sair" }));

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/login?motivo=saiu"));
  expect(fetchSpy).toHaveBeenCalledWith(
    "/api/auth/logout",
    expect.objectContaining({ method: "POST" }),
  );
});
