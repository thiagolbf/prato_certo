import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { CampoFormulario } from "./CampoFormulario";

test("CampoFormulario mostra o erro junto ao campo", () => {
  render(<CampoFormulario rotulo="Nome" erro="Informe o nome" />);

  const campo = screen.getByRole("textbox", { name: "Nome" });
  expect(campo).toHaveAttribute("aria-invalid", "true");
  expect(campo).toHaveAccessibleDescription("Informe o nome");
  expect(screen.getByText("Informe o nome")).toBeInTheDocument();
});
