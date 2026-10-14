import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ProvedorSessao, type Perfil } from "@/lib/sessao";

import PaginaRegistrar from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

function responder(corpo: unknown, status = 200) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(corpo), { status }));
}

function renderizar(perfil: Perfil) {
  return render(
    <ProvedorSessao valor={{ nome: "Ana", login: "ana", perfil, diaOperacional: "2026-10-10" }}>
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

  test("CA-04 — falha de rede não é silenciada e oferece reenviar", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      String(url).endsWith("/cardapio/vigente")
        ? Promise.resolve(new Response(JSON.stringify(cardapioDoDia), { status: 200 }))
        : Promise.reject(new TypeError("Failed to fetch")),
    );
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("Venda NÃO registrada — sem conexão");
    expect(within(aviso).getByRole("button", { name: "Reenviar" })).toBeInTheDocument();
    expect(sessionStorage.getItem("controle-pendencias-venda")).toContain("Feijoada");
  });

  test("reenvio usa a mesma chave", async () => {
    let falhar = true;
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      if (String(url).endsWith("/cardapio/vigente")) {
        return Promise.resolve(new Response(JSON.stringify(cardapioDoDia), { status: 200 }));
      }
      if (falhar) return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve(new Response(JSON.stringify({ id: 1, item_id: 1, quantidade: 1 }), { status: 200 }));
    });
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    const aviso = await screen.findByRole("alert");

    falhar = false;
    fireEvent.click(within(aviso).getByRole("button", { name: "Reenviar" }));

    await vi.waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    const envios = fetchSpy.mock.calls
      .filter(([url]) => String(url).endsWith("/api/vendas"))
      .map(([, init]) => JSON.parse((init as RequestInit).body as string).chave_idempotencia);
    expect(envios).toHaveLength(2);
    expect(envios[1]).toBe(envios[0]);
  });

  test("CA-58 — pendência descartada não é enviada", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      String(url).endsWith("/cardapio/vigente")
        ? Promise.resolve(new Response(JSON.stringify(cardapioDoDia), { status: 200 }))
        : Promise.reject(new TypeError("Failed to fetch")),
    );
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    const aviso = await screen.findByRole("alert");

    fireEvent.click(within(aviso).getByRole("button", { name: "Descartar" }));
    expect(await screen.findByText("Descartar esta venda?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Descartar venda" }));

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    const envios = fetchSpy.mock.calls.filter(([url]) => String(url).endsWith("/api/vendas"));
    expect(envios).toHaveLength(1);
  });

  test("401 no envio mostra sessão expirada e deixa a venda pendente para o mesmo usuário", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      Promise.resolve(
        String(url).endsWith("/cardapio/vigente")
          ? new Response(JSON.stringify(cardapioDoDia), { status: 200 })
          : new Response("{}", { status: 401 }),
      ),
    );
    renderizar("OPERADOR");

    await abrirPainelPF();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("Sua sessão expirou. A venda NÃO foi registrada.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Entrar novamente" })).toBeInTheDocument();
    expect(sessionStorage.getItem("controle-pendencias-venda")).toContain("Feijoada");
  });

  test("CA-59 — outro usuário no aparelho descarta a pendência com aviso e não envia nada", async () => {
    const guardada = {
      chave: "0b6f2c1e-7d0a-4a52-9f0e-3c1f8e2a9b10",
      itemId: 1,
      nomePrato: "Feijoada",
      formato: "PF",
      quantidade: 2,
      usuario: "joao",
      diaOperacional: "2026-10-10",
    };
    sessionStorage.setItem("controle-pendencias-venda", JSON.stringify([guardada]));
    const fetchSpy = responder(cardapioDoDia);
    renderizar("OPERADOR"); // sessão de "ana"

    const aviso = await screen.findByText("Uma venda pendente foi descartada sem ser registrada");
    expect(aviso).toBeInTheDocument();
    expect(screen.getByText(/2× Feijoada · PF/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar" })).not.toBeInTheDocument();
    expect(sessionStorage.getItem("controle-pendencias-venda")).toBe("[]");
    expect(fetchSpy.mock.calls.filter(([url]) => String(url).endsWith("/api/vendas"))).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Entendi" }));
    expect(screen.queryByText("Uma venda pendente foi descartada sem ser registrada")).not.toBeInTheDocument();
  });

  test("CA-59 — o mesmo usuário continua com a pendência e pode reenviar", async () => {
    const guardada = {
      chave: "0b6f2c1e-7d0a-4a52-9f0e-3c1f8e2a9b10",
      itemId: 1,
      nomePrato: "Feijoada",
      formato: "PF",
      quantidade: 2,
      usuario: "ana",
      diaOperacional: "2026-10-10",
    };
    sessionStorage.setItem("controle-pendencias-venda", JSON.stringify([guardada]));
    responder(cardapioDoDia);
    renderizar("OPERADOR");

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("2× Feijoada · PF");
    expect(within(aviso).getByRole("button", { name: "Reenviar" })).toBeInTheDocument();
    expect(screen.queryByText("Uma venda pendente foi descartada sem ser registrada")).not.toBeInTheDocument();
  });

  test("CA-60 — pendência de outro dia operacional é descartada com aviso e a origem", async () => {
    const guardada = {
      chave: "0b6f2c1e-7d0a-4a52-9f0e-3c1f8e2a9b10",
      itemId: 1,
      nomePrato: "Feijoada",
      formato: "PF",
      quantidade: 1,
      usuario: "ana",
      diaOperacional: "2026-10-09",
    };
    sessionStorage.setItem("controle-pendencias-venda", JSON.stringify([guardada]));
    const fetchSpy = responder(cardapioDoDia);
    renderizar("OPERADOR");

    expect(await screen.findByText("Uma venda pendente foi descartada sem ser registrada")).toBeInTheDocument();
    expect(screen.getByText(/ficou pendente em 09\/10/)).toBeInTheDocument();
    expect(screen.getByText("Se ela aconteceu, avise o responsável.")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.filter(([url]) => String(url).endsWith("/api/vendas"))).toHaveLength(0);
  });

  test("CA-59 — outra conta com o mesmo nome não herda a pendência", async () => {
    const guardada = {
      chave: "0b6f2c1e-7d0a-4a52-9f0e-3c1f8e2a9b10",
      itemId: 1,
      nomePrato: "Feijoada",
      formato: "PF",
      quantidade: 1,
      usuario: "ana2", // outro login, mesmo nome "Ana"
      diaOperacional: "2026-10-10",
    };
    sessionStorage.setItem("controle-pendencias-venda", JSON.stringify([guardada]));
    responder(cardapioDoDia);
    renderizar("OPERADOR"); // sessão de "ana"

    expect(await screen.findByText("Uma venda pendente foi descartada sem ser registrada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar" })).not.toBeInTheDocument();
  });
});
