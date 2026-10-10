import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import PaginaUsuarios from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const operador = {
  id: 2,
  nome: "Carla",
  login: "carla",
  perfil: "OPERADOR",
  ativo: true,
  bloqueado_ate: "2026-10-10T12:30:00Z",
};

function renderizar() {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([operador]), { status: 200 }));
  return render(
    <ProvedorSessao valor={{ nome: "Bruno", perfil: "ADMIN", diaOperacional: "2026-10-10" }}>
      <PaginaUsuarios />
    </ProvedorSessao>,
  );
}

test("mostra bloqueado até", async () => {
  renderizar();

  expect(await screen.findByText(/Bloqueado até 09:30/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Redefinir senha" })).toBeInTheDocument();
});

test("formulário não tem campo de perfil", async () => {
  renderizar();

  fireEvent.click(await screen.findByRole("button", { name: "Novo operador" }));

  expect(screen.queryByLabelText(/perfil/i)).not.toBeInTheDocument();
  expect(screen.getByLabelText(/Senha inicial/)).toBeInTheDocument();
});

test("senha curta mostra a mensagem", async () => {
  renderizar();

  fireEvent.click(await screen.findByRole("button", { name: "Novo operador" }));
  fireEvent.change(screen.getByLabelText("Nome"), { target: { value: "Ana" } });
  fireEvent.change(screen.getByLabelText(/Usuário/), { target: { value: "ana" } });
  fireEvent.change(screen.getByLabelText(/Senha inicial/), { target: { value: "curta" } });
  fireEvent.click(screen.getByRole("button", { name: "Cadastrar operador" }));

  expect(screen.getByText("A senha precisa ter pelo menos 8 caracteres.")).toBeInTheDocument();
});
