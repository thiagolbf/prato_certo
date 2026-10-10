"use client";

import Link from "next/link";

import styles from "./MenuMais.module.css";

const ITENS = [
  { href: "/minhas-vendas", rotulo: "Minhas vendas de hoje" },
  { href: "/catalogo/proteinas", rotulo: "Proteínas" },
  { href: "/catalogo/pratos", rotulo: "Pratos" },
  { href: "/catalogo/itens", rotulo: "Itens" },
  { href: "/usuarios", rotulo: "Usuários" },
  { href: "/conta/senha", rotulo: "Trocar minha senha" },
];

// Painel do menu "Mais" (ADMIN). Aberto/fechado é decidido pelo AppShell.
export function MenuMais({ onSair, onFechar }: { onSair: () => void; onFechar: () => void }) {
  return (
    <div className={styles.painel} role="dialog" aria-label="Mais opções">
      <ul className={styles.lista}>
        {ITENS.map((item) => (
          <li key={item.href}>
            <Link className={styles.item} href={item.href} onClick={onFechar}>
              {item.rotulo}
            </Link>
          </li>
        ))}
        <li>
          <button className={styles.item} type="button" onClick={onSair}>
            Sair
          </button>
        </li>
      </ul>
      <button className={styles.voltar} type="button" onClick={onFechar}>
        Voltar
      </button>
    </div>
  );
}
