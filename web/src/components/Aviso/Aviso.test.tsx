import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Aviso } from "./Aviso";

test("Aviso de falha tem role alert", () => {
  render(<Aviso variante="falha">Venda NÃO registrada</Aviso>);

  expect(screen.getByRole("alert")).toHaveTextContent("Venda NÃO registrada");
});

test("Aviso informativo tem role status", () => {
  render(<Aviso variante="informacao">Cardápio herdado</Aviso>);

  expect(screen.getByRole("status")).toHaveTextContent("Cardápio herdado");
});
