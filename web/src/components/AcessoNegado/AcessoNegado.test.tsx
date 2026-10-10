import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ProvedorSessao } from "@/lib/sessao";

import { RotaRestrita } from "./AcessoNegado";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

test("rota de ADMIN mostra AcessoNegado ao Operador", () => {
  render(
    <ProvedorSessao valor={{ nome: "Ana", perfil: "OPERADOR", diaOperacional: "2026-10-10" }}>
      <RotaRestrita perfis={["ADMIN"]}>
        <p>Conteúdo de ADMIN</p>
      </RotaRestrita>
    </ProvedorSessao>,
  );

  expect(screen.getByRole("link", { name: "Voltar ao registro" })).toHaveAttribute(
    "href",
    "/registrar",
  );
  expect(screen.queryByText("Conteúdo de ADMIN")).not.toBeInTheDocument();
});
