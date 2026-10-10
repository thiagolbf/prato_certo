import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ProvedorSessao, type Perfil } from "@/lib/sessao";

import PaginaRegistrar from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

function responder(corpo: unknown, status = 200) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(corpo), { status }));
}

function renderizar(perfil: Perfil) {
  return render(
    <ProvedorSessao valor={{ nome: "Ana", perfil, diaOperacional: "2026-10-10" }}>
      <PaginaRegistrar />
    </ProvedorSessao>,
  );
}

const itemPF = {
  item_id: 1,
  nome_prato: "Feijoada",
  nome_proteina: "Carne",
  formato: "PF",
  gramas_por_porcao: 400,
  preco: "18.00",
};

const cardapioDoDia = { data: "2026-10-10", tipo: "PROPRIO", data_origem: null, itens: [itemPF] };

// Abre o painel tocando a célula PF da linha do prato.
async function abrirPainelPF() {
  const linha = (await screen.findByRole("rowheader", { name: "Feijoada" })).closest("[role=row]");
  fireEvent.click(within(linha as HTMLElement).getAllByRole("button")[0]);
}

describe("UI-02 — registro", () => {
  test("CA-10 — primeiro uso mostra estado vazio sem itens tocáveis", async () => {
    responder({ data: "2026-10-10", tipo: "VAZIO", data_origem: null, itens: [] });
    renderizar("OPERADOR");

    expect(
      await screen.findByText("Chame o responsável para montar o cardápio do dia."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /PF/ })).not.toBeInTheDocument();
  });

  test("herdado mostra a data de origem e o aviso só ao ADMIN", async () => {
    responder({ data: "2026-10-10", tipo: "HERDADO", data_origem: "2026-10-09", itens: [itemPF] });
    const { unmount } = renderizar("OPERADOR");

    expect(await screen.findByText("Herdado de 09/10")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Revisar cardápio" })).not.toBeInTheDocument();
    unmount();

    responder({ data: "2026-10-10", tipo: "HERDADO", data_origem: "2026-10-09", itens: [itemPF] });
    renderizar("ADMIN");

    expect(await screen.findByRole("link", { name: "Revisar cardápio" })).toBeInTheDocument();
  });

  test("CA-01 — confirma o registro sem aguardar o servidor", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((url) => {
        if (String(url).endsWith("/cardapio/vigente")) {
          return Promise.resolve(new Response(JSON.stringify(cardapioDoDia), { status: 200 }));
        }
        return new Promise(() => {}); // o servidor nunca responde nesta resposta
      });
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(screen.getByRole("status")).toHaveTextContent("Registrado: 1× Feijoada · PF");
    const envio = fetchSpy.mock.calls.find(([url]) => String(url).endsWith("/api/vendas"));
    expect(envio).toBeDefined();
    const corpo = JSON.parse((envio![1] as RequestInit).body as string);
    expect(corpo.quantidade).toBe(1);
    expect(corpo.chave_idempotencia).toMatch(/^[0-9a-f-]{36}$/);
  });

  test("CA-02 — envia a quantidade ajustada", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            String(url).endsWith("/cardapio/vigente") ? cardapioDoDia : { id: 1, item_id: 1, quantidade: 3 },
          ),
          { status: 200 },
        ),
      ),
    );
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Aumentar" }));
    fireEvent.click(screen.getByRole("button", { name: "Aumentar" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    const envio = fetchSpy.mock.calls.find(([url]) => String(url).endsWith("/api/vendas"));
    expect(JSON.parse((envio![1] as RequestInit).body as string).quantidade).toBe(3);
  });

  test("CA-05 — mais desabilita em 20 e informa o limite", async () => {
    responder(cardapioDoDia);
    renderizar("OPERADOR");

    await abrirPainelPF();
    for (let i = 1; i < 20; i++) fireEvent.click(screen.getByRole("button", { name: "Aumentar" }));

    expect(screen.getByRole("button", { name: "Aumentar" })).toBeDisabled();
    expect(
      screen.getByText(
        "Máximo de 20 por lançamento. Para mais, confirme este e faça outro lançamento.",
      ),
    ).toBeInTheDocument();
  });

  test("422 mostra recusado sem reenviar", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      Promise.resolve(
        new Response(
          JSON.stringify(String(url).endsWith("/cardapio/vigente") ? cardapioDoDia : { detail: "x" }),
          { status: String(url).endsWith("/cardapio/vigente") ? 200 : 422 },
        ),
      ),
    );
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("Venda NÃO registrada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Atualizar cardápio" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar" })).not.toBeInTheDocument();
  });
});
