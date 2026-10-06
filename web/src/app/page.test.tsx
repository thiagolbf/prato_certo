import { redirect } from "next/navigation";
import { expect, test, vi } from "vitest";

import Home from "./page";

vi.mock("next/navigation", () => ({ redirect: vi.fn() }));

test("a raiz leva direto ao registro de venda", () => {
  Home();

  expect(redirect).toHaveBeenCalledWith("/registrar");
});
