import type { ReactNode } from "react";

import styles from "./Aviso.module.css";

export type VarianteAviso = "falha" | "aviso" | "informacao" | "sucesso";

// Falha é anunciada como alerta e fica na tela até ser tratada; as demais são só informativas.
export function Aviso({
  variante,
  children,
}: {
  variante: VarianteAviso;
  children: ReactNode;
}) {
  const papel = variante === "falha" ? "alert" : "status";
  return (
    <div className={`${styles.base} ${styles[variante]}`} role={papel}>
      {children}
    </div>
  );
}
