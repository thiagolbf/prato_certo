import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Toast } from "./Toast";

test("Toast anuncia a confirmação como status", () => {
  render(<Toast>✓ Registrado: 1× Frango grelhado · PF</Toast>);

  expect(screen.getByRole("status")).toHaveTextContent("Registrado");
});
