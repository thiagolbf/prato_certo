// @vitest-environment jsdom
import { describe, expect, test, vi } from "vitest";

import { criarClienteApi, ErroApi, SessaoExpirada } from "./api";

describe("cliente HTTP", () => {
  test("401 redireciona para o login com sessão expirada", async () => {
    const aoSessaoExpirada = vi.fn();
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 401 }));
    const api = criarClienteApi(aoSessaoExpirada, fetchImpl);

    await expect(api.get("/auth/me")).rejects.toBeInstanceOf(SessaoExpirada);
    expect(aoSessaoExpirada).toHaveBeenCalledOnce();
  });

  test("chama caminhos relativos /api com o cookie do mesmo site", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const api = criarClienteApi(() => {}, fetchImpl);

    await api.post("/auth/logout");

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });

  test("resposta de erro vira ErroApi com o status, sem detalhe técnico", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "interno" }), { status: 500 }),
    );
    const api = criarClienteApi(() => {}, fetchImpl);

    await expect(api.get("/auth/me")).rejects.toBeInstanceOf(ErroApi);
  });
});
