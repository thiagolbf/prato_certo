import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import PaginaProteinas from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const frango = { id: 1, nome: "Frango", ativo: true, pratos_ativos: 2 };
const carneDesativada = { id: 2, nome: "Carne", ativo: false, pratos_ativos: 0 };

function responder(mapa: (url: string, metodo: string) => { status: number; corpo?: unknown }) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
    const { status, corpo } = mapa(String(url), (init as RequestInit | undefined)?.method ?? "GET");
    return Promise.resolve(new Response(corpo === undefined ? null : JSON.stringify(corpo), { status }));
  });
}

describe("UI-09 — proteínas", () => {
  test("CA-62 — desativação bloqueada lista os dependentes", async () => {
    responder((url, metodo) => {
      if (metodo === "POST" && url.endsWith("/desativar")) {
        return {
          status: 409,
          corpo: {
            detail:
              "Não é possível desativar: usada pelo prato ativo Frango com arroz, Frango xis. Desative esses pratos antes.",
          },
        };
      }
      return { status: 200, corpo: [frango] };
    });
    render(<PaginaProteinas />);

    fireEvent.click(await screen.findByRole("button", { name: "Desativar" }));
    fireEvent.click(screen.getByRole("button", { name: "Desativar proteína" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Frango com arroz, Frango xis");
    expect(screen.getByRole("link", { name: "Ver os pratos" })).toHaveAttribute("href", "/catalogo/pratos");
  });

  test("duplicado desativado oferece reativar", async () => {
    const fetchSpy = responder(() => ({ status: 200, corpo: [carneDesativada] }));
    render(<PaginaProteinas />);

    fireEvent.click(await screen.findByRole("button", { name: "Nova proteína" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Nome" }), { target: { value: " carne " } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    const aviso = await screen.findByRole("status");
    expect(aviso).toHaveTextContent("Já existe uma proteína desativada com esse nome.");
    expect(within(aviso).getByRole("button", { name: "Reativar" })).toBeInTheDocument();
    const criacoes = fetchSpy.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(criacoes).toHaveLength(0);
  });

  test("filtro mostra desativados", async () => {
    responder(() => ({ status: 200, corpo: [frango, carneDesativada] }));
    render(<PaginaProteinas />);

    expect(await screen.findByText("Frango")).toBeInTheDocument();
    expect(screen.queryByText("Carne")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Mostrar desativados" }));

    expect(screen.getByText("Carne")).toBeInTheDocument();
  });
});
