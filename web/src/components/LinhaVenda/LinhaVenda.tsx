import { Etiqueta } from "@/components/Etiqueta/Etiqueta";
import type { VendaDoDia } from "@/lib/vendas";

import styles from "./LinhaVenda.module.css";

// Horário no fuso do restaurante (RN-27). A API manda instante UTC.
export function formatarHorario(instante: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(instante));
}

// Linha de venda. Na variante do Operador não há preço nem valor (RN-40, CA-36).
// A cancelada aparece riscada e com a etiqueta (CA-54).
export function LinhaVenda({ venda }: { venda: VendaDoDia }) {
  return (
    <li className={`${styles.linha} ${venda.cancelada ? styles.cancelada : ""}`}>
      <time className={styles.horario} dateTime={venda.horario}>
        {formatarHorario(venda.horario)}
      </time>
      <span className={styles.descricao}>
        {venda.quantidade}× {venda.prato_nome} · {venda.formato}
      </span>
      {venda.cancelada && <Etiqueta variante="cancelada" />}
    </li>
  );
}
