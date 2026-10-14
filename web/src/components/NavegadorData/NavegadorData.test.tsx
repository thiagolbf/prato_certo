import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { NavegadorData } from "./NavegadorData";

test("NavegadorData respeita o limite superior", () => {
  const aoMudar = vi.fn();
  render(<NavegadorData valor="2026-10-10" limiteSuperior="2026-10-10" aoMudar={aoMudar} />);

  expect(screen.getByRole("button", { name: "Dia seguinte" })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "Dia anterior" }));
  expect(aoMudar).toHaveBeenCalledWith("2026-10-09");
});
