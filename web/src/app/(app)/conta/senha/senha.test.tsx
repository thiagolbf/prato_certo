import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import PaginaTrocarSenha from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

function preencher(atual: string, nova: string, repeticao: string) {
  fireEvent.change(screen.getByLabelText("Senha atual"), { target: { value: atual } });
  fireEvent.change(screen.getByLabelText("Nova senha"), { target: { value: nova } });
  fireEvent.change(screen.getByLabelText("Repita a nova senha"), { target: { value: repeticao } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));
}

function renderizar(perfil: "ADMIN" | "OPERADOR") {
  return render(
    <ProvedorSessao valor={{ nome: "Bruno", perfil, diaOperacional: "2026-10-10" }}>
      <PaginaTrocarSenha />
    </ProvedorSessao>,
  );
}

test("repetição diferente mostra erro", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  renderizar("ADMIN");

  preencher("senha-atual-1", "nova-senha-123", "outra-senha-123");

  expect(screen.getByText("As senhas não conferem.")).toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
});

test("senha atual incorreta marca o campo", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Senha atual incorreta ou conta bloqueada temporariamente." }), {
      status: 422,
    }),
  );
  renderizar("ADMIN");

  preencher("errada-123", "nova-senha-123", "nova-senha-123");

  expect(await screen.findByText("Senha atual incorreta ou conta bloqueada temporariamente.")).toBeInTheDocument();
  expect(screen.getByLabelText("Senha atual")).toHaveAttribute("aria-invalid", "true");
});

test("Operador vê AcessoNegado", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  renderizar("OPERADOR");

  expect(screen.getByRole("link", { name: "Voltar ao registro" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Senha atual")).not.toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
});
