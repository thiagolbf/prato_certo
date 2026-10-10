"use client";

import { createContext, useContext, type ReactNode } from "react";

// Espelha `RespostaUsuario` da API (GET /api/auth/me).
export type Perfil = "ADMIN" | "OPERADOR";

export type Sessao = {
  nome: string;
  perfil: Perfil;
  diaOperacional: string;
};

const ContextoSessao = createContext<Sessao | null>(null);

export function ProvedorSessao({ valor, children }: { valor: Sessao; children: ReactNode }) {
  return <ContextoSessao.Provider value={valor}>{children}</ContextoSessao.Provider>;
}

export function useSessao(): Sessao {
  const sessao = useContext(ContextoSessao);
  if (!sessao) throw new Error("useSessao usado fora do ProvedorSessao");
  return sessao;
}
