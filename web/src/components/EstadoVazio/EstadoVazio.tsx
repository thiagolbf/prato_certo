import type { ReactNode } from "react";

import styles from "./EstadoVazio.module.css";

// Mensagem de lista vazia com a ação sugerida.
export function EstadoVazio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <section className={styles.vazio}>
      <p className={styles.titulo}>{titulo}</p>
      {children}
    </section>
  );
}
