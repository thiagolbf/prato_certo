import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import VendasDaData from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

test("O Operador abrindo /vendas vê AcessoNegado, sem chamar a API de ADMIN", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  render(
    <ProvedorSessao valor={{ nome: "Ana", perfil: "OPERADOR", diaOperacional: "2026-10-10" }}>
      <VendasDaData />
    </ProvedorSessao>,
  );

  expect(screen.getByRole("link", { name: "Voltar ao registro" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Vendas da data" })).not.toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
  fetchSpy.mockRestore();
});
