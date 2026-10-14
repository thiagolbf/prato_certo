import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test } from "vitest";

import { PainelInferior } from "./PainelInferior";

function Teste() {
  const [aberto, setAberto] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setAberto(true)}>
        Abrir
      </button>
      <PainelInferior aberto={aberto} titulo="Opções" aoFechar={() => setAberto(false)}>
        <button type="button">Primeiro</button>
        <button type="button">Último</button>
      </PainelInferior>
    </>
  );
}

test("PainelInferior prende e devolve o foco", () => {
  render(<Teste />);
  const abrir = screen.getByRole("button", { name: "Abrir" });
  abrir.focus();

  fireEvent.click(abrir);
  expect(screen.getByRole("button", { name: "Primeiro" })).toHaveFocus();

  screen.getByRole("button", { name: "Voltar" }).focus();
  fireEvent.keyDown(document.activeElement as Element, { key: "Tab" });
  expect(screen.getByRole("button", { name: "Primeiro" })).toHaveFocus();

  fireEvent.keyDown(document.activeElement as Element, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(abrir).toHaveFocus();
});
