import { render } from "@testing-library/react";
import { expect, test } from "vitest";

import { Skeleton } from "./Skeleton";

test("Skeleton monta uma linha por item e fica escondido de leitores de tela", () => {
  const { container } = render(<Skeleton linhas={4} />);

  expect(container.querySelectorAll("span")).toHaveLength(4);
  expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
});
