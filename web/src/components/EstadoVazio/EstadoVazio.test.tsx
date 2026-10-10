import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { EstadoVazio } from "./EstadoVazio";

test("EstadoVazio mostra o título e a ação sugerida", () => {
  render(<EstadoVazio titulo="Nenhuma venda hoje">Registre a primeira</EstadoVazio>);

  expect(screen.getByText("Nenhuma venda hoje")).toBeInTheDocument();
  expect(screen.getByText("Registre a primeira")).toBeInTheDocument();
});
