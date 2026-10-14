import type { ReactNode } from "react";

import styles from "./Toast.module.css";

// Confirmação curta de sucesso; anunciada como status, sem roubar o foco.
export function Toast({ children }: { children: ReactNode }) {
  return (
    <div className={styles.toast} role="status">
      {children}
    </div>
  );
}
