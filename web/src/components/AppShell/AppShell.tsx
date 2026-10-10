"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { api, SessaoExpirada } from "@/lib/api";
import { type Perfil, useSessao } from "@/lib/sessao";
import { MenuMais } from "@/components/MenuMais/MenuMais";

import styles from "./AppShell.module.css";

type Item = { href: string; rotulo: string };

// Navegação inferior por perfil (SPEC-UI seção 5, AppShell).
const NAVEGACAO: Record<Perfil, Item[]> = {
  OPERADOR: [
    { href: "/registrar", rotulo: "Registrar" },
    { href: "/minhas-vendas", rotulo: "Minhas vendas" },
  ],
  ADMIN: [
    { href: "/registrar", rotulo: "Registrar" },
    { href: "/vendas", rotulo: "Vendas" },
    { href: "/fechamento", rotulo: "Fechamento" },
    { href: "/cardapio", rotulo: "Cardápio" },
  ],
};

export function AppShell({ children }: { children: ReactNode }) {
  const { nome, perfil } = useSessao();
  const caminho = usePathname();
  const router = useRouter();
  const [maisAberto, setMaisAberto] = useState(false);

  async function sair() {
    // Sair é POST (RN-54, RN-42). Mesmo se a chamada falhar, o usuário vai ao login.
    try {
      await api.post("/auth/logout");
    } catch (erro) {
      // Sessão já expirada: o cliente da API já levou ao login com o motivo certo.
      if (erro instanceof SessaoExpirada) return;
    }
    router.replace("/login?motivo=saiu");
  }

  return (
    <div className={styles.casca}>
      <header className={styles.topo}>
        <div className={styles.identidade}>
          <span className={styles.titulo}>Controle de PF e Marmitas</span>
          <span className={styles.usuario}>
            {nome} · {perfil === "ADMIN" ? "ADMIN" : "Operador"}
          </span>
        </div>
        <button className={styles.sair} type="button" onClick={sair}>
          Sair
        </button>
      </header>

      <main className={styles.conteudo}>{children}</main>

      {perfil === "ADMIN" && maisAberto && (
        <MenuMais onSair={sair} onFechar={() => setMaisAberto(false)} />
      )}

      <nav className={styles.navegacao} aria-label="Principal">
        <ul className={styles.lista}>
          {NAVEGACAO[perfil].map((item) => (
            <li key={item.href}>
              <Link
                className={styles.item}
                href={item.href}
                aria-current={caminho === item.href ? "page" : undefined}
              >
                {item.rotulo}
              </Link>
            </li>
          ))}
          {perfil === "ADMIN" && (
            <li>
              <button
                className={styles.item}
                type="button"
                aria-expanded={maisAberto}
                onClick={() => setMaisAberto((aberto) => !aberto)}
              >
                Mais
              </button>
            </li>
          )}
        </ul>
      </nav>
    </div>
  );
}
