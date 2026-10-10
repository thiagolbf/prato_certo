"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { type Perfil, useSessao } from "@/lib/sessao";

import styles from "./AcessoNegado.module.css";

export function AcessoNegado() {
  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Esta tela não está disponível para o seu perfil.</h1>
      <Link className={styles.voltar} href="/registrar">
        Voltar ao registro
      </Link>
    </section>
  );
}

// Guarda de rota por perfil (ADR-009: autorização é dependência da rota, não da entidade).
// Quem não tem o perfil nem chega a montar o conteúdo, então não dispara chamadas de ADMIN.
export function RotaRestrita({ perfis, children }: { perfis: Perfil[]; children: ReactNode }) {
  const { perfil } = useSessao();
  if (!perfis.includes(perfil)) return <AcessoNegado />;
  return children;
}
