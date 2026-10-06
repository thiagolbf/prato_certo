import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

function Saudacao({ nome }: { nome: string }) {
  return <h1>Olá, {nome}</h1>;
}

test("o Vitest renderiza um componente com a Testing Library e os matchers do jest-dom", () => {
  render(<Saudacao nome="balcão" />);

  expect(screen.getByRole("heading", { name: "Olá, balcão" })).toBeInTheDocument();
});
