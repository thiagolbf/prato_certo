import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ErroCarregamento } from "./ErroCarregamento";

test("ErroCarregamento chama o retry", () => {
  const onTentarDeNovo = vi.fn();
  render(<ErroCarregamento onTentarDeNovo={onTentarDeNovo} />);

  fireEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));

  expect(onTentarDeNovo).toHaveBeenCalledOnce();
});
