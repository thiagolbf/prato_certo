"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";

import styles from "./catalogo.module.css";

const ABAS = [
  { href: "/catalogo/proteinas", rotulo: "Proteínas" },
  { href: "/catalogo/pratos", rotulo: "Pratos" },
  { href: "/catalogo/itens", rotulo: "Itens" },
];

// Abas do catálogo, só para o ADMIN (UI-09 a UI-11).
export default function LayoutCatalogo({ children }: { children: ReactNode }) {
  const caminho = usePathname();
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <div className={styles.bloco}>
        <nav aria-label="Catálogo">
          <ul className={styles.abas}>
            {ABAS.map((aba) => (
              <li key={aba.href}>
                <Link
                  className={styles.aba}
                  href={aba.href}
                  aria-current={caminho === aba.href ? "page" : undefined}
                >
                  {aba.rotulo}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        {children}
      </div>
    </RotaRestrita>
  );
}
