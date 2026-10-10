import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Etiqueta, type VarianteEtiqueta } from "./Etiqueta";

const ROTULOS: [VarianteEtiqueta, string][] = [
  ["cancelada", "Cancelada"],
  ["desativado", "Desativado"],
  ["herdado", "Herdado"],
  ["proprio", "Próprio"],
  ["somenteLeitura", "Somente leitura"],
];

test("Etiqueta renderiza cada variante", () => {
  for (const [variante, rotulo] of ROTULOS) {
    const { unmount } = render(<Etiqueta variante={variante} />);

    expect(screen.getByText(rotulo)).toBeInTheDocument();
    unmount();
  }
});
