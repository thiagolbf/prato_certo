import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { FormularioEntrar } from "./FormularioEntrar";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

afterEach(() => {
  vi.restoreAllMocks();
  replace.mockClear();
});

function preencherEEnviar() {
  fireEvent.change(screen.getByRole("textbox", { name: "Usuário" }), {
    target: { value: "ana" },
  });
  fireEvent.change(document.querySelector('input[name="senha"]') as HTMLInputElement, {
    target: { value: "segredo" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

test("mostra a mensagem única para 401", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "x" }), { status: 401 }),
  );
  render(<FormularioEntrar />);

  preencherEEnviar();

  expect(
    await screen.findByText(
      "Usuário ou senha inválidos. Se o problema continuar, fale com o responsável.",
    ),
  ).toBeInTheDocument();
  expect(replace).not.toHaveBeenCalled();
});

test("mostra o aviso de limite para 429", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "x" }), { status: 429 }),
  );
  render(<FormularioEntrar />);

  preencherEEnviar();

  expect(
    await screen.findByText("Muitas tentativas em pouco tempo. Aguarde alguns segundos e tente de novo."),
  ).toBeInTheDocument();
});

test("mostra \"Você saiu.\" depois de Sair", () => {
  render(<FormularioEntrar motivo="saiu" />);

  expect(screen.getByText("Você saiu.")).toBeInTheDocument();
});

test("sucesso leva ao registro", async () => {
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(JSON.stringify({ nome: "Ana", perfil: "OPERADOR", dia_operacional: "2026-10-10" }), {
        status: 200,
      }),
    );
  render(<FormularioEntrar />);

  preencherEEnviar();

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/registrar"));
  expect(fetchSpy).toHaveBeenCalledWith(
    "/api/auth/login",
    expect.objectContaining({ method: "POST" }),
  );
});
