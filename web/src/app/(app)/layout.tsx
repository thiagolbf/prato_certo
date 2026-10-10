"use client";

import { useEffect, useState, type ReactNode } from "react";

import { AppShell } from "@/components/AppShell/AppShell";
import { api } from "@/lib/api";
import { ProvedorSessao, type Perfil, type Sessao } from "@/lib/sessao";

// Espelha `RespostaUsuario` de GET /api/auth/me.
type RespostaMe = { nome: string; perfil: Perfil; dia_operacional: string };

// Guarda das telas autenticadas: sem sessão válida, `api` já leva ao login (401).
export default function LayoutAutenticado({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(null);

  useEffect(() => {
    let ativo = true;
    api
      .get<RespostaMe>("/auth/me")
      .then((resposta) => {
        if (!ativo) return;
        setSessao({
          nome: resposta.nome,
          perfil: resposta.perfil,
          diaOperacional: resposta.dia_operacional,
        });
      })
      .catch(() => undefined);
    return () => {
      ativo = false;
    };
  }, []);

  if (!sessao) return <main aria-busy="true" />;

  return (
    <ProvedorSessao valor={sessao}>
      <AppShell>{children}</AppShell>
    </ProvedorSessao>
  );
}
