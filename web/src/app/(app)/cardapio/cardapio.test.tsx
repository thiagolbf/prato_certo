import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import PaginaCardapio from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
});

const feijoada = { item_id: 1, nome_prato: "Feijoada", nome_proteina: "Carne", formato: "PF", gramas_por_porcao: 400, preco: "18.00" };
const catalogo = [
  { id: 1, prato_id: 10, prato_nome: "Feijoada", nome: "Feijoada", formato: "PF", gramas_por_porcao: 400, preco: "18.00", ativo: true },
  { id: 2, prato_id: 11, prato_nome: "Strogonoff", nome: "Strogonoff", formato: "PF", gramas_por_porcao: 300, preco: "20.00", ativo: true },
];

function mockApi(cardapio: object, postar?: () => Promise<Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
    const caminho = String(url);
    if ((init as RequestInit | undefined)?.method === "POST") {
      return postar ? postar() : Promise.resolve(new Response(null, { status: 204 }));
    }
    if (caminho.includes("/cardapio?data=")) return Promise.resolve(new Response(JSON.stringify(cardapio), { status: 200 }));
    if (caminho.endsWith("/itens")) return Promise.resolve(new Response(JSON.stringify(catalogo), { status: 200 }));
    return Promise.resolve(new Response(JSON.stringify({ vendas: [] }), { status: 200 }));
  });
}

function renderizar() {
  return render(
    <ProvedorSessao valor={{ nome: "Thiago", perfil: "ADMIN", diaOperacional: "2026-10-10" }}>
      <PaginaCardapio />
    </ProvedorSessao>,
  );
}

describe("UI-08 — cardápio da data", () => {
  test("CA-49 — data passada é somente leitura", async () => {
    mockApi({ data: "2026-10-01", tipo: "PROPRIO", data_origem: null, itens: [feijoada], passada: true });
    renderizar();

    expect(await screen.findByText("Feijoada · PF")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar cardápio" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar este cardápio" })).not.toBeInTheDocument();
  });

  test("CA-61 — salvar sem itens mostra validação e não envia", async () => {
    const fetchSpy = mockApi({ data: "2026-10-10", tipo: "PROPRIO", data_origem: null, itens: [feijoada], passada: false });
    renderizar();

    fireEvent.click(await screen.findByRole("button", { name: "Editar cardápio" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Feijoada/ }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(screen.getByText("Selecione pelo menos um item. Um cardápio não pode ficar vazio.")).toBeInTheDocument();
    const posts = fetchSpy.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(posts).toHaveLength(0);
  });

  test("erro de envio preserva a seleção", async () => {
    mockApi(
      { data: "2026-10-10", tipo: "PROPRIO", data_origem: null, itens: [feijoada], passada: false },
      () => Promise.resolve(new Response(JSON.stringify({ detail: "Falha" }), { status: 500 })),
    );
    renderizar();

    fireEvent.click(await screen.findByRole("button", { name: "Editar cardápio" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Strogonoff/ }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByText("Não foi possível salvar agora. Tente de novo.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Salvar" })).not.toBeDisabled());
    expect(screen.getByRole("checkbox", { name: /Feijoada/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Strogonoff/ })).toBeChecked();
  });
});
