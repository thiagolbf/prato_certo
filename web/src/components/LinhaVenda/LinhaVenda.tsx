import { Etiqueta } from "@/components/Etiqueta/Etiqueta";
import { formatarMoeda } from "@/lib/formato";
import type { VendaDaData, VendaDoDia } from "@/lib/vendas";

import styles from "./LinhaVenda.module.css";

// Horário no fuso do restaurante (RN-27). A API manda instante UTC.
export function formatarHorario(instante: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(instante));
}

// Variante do Operador: sem preço nem valor (RN-40, CA-36). Variante do ADMIN: com autor, preço,
// valor e, se cancelada, quem cancelou, quando e o motivo (RN-51, CA-50).
export function LinhaVenda({
  venda,
  aoCancelar,
}: {
  venda: VendaDoDia | VendaDaData;
  aoCancelar?: () => void;
}) {
  const admin = "autor" in venda ? venda : null;

  return (
    <li className={`${styles.linha} ${venda.cancelada ? styles.cancelada : ""}`}>
      <time className={styles.horario} dateTime={venda.horario}>
        {formatarHorario(venda.horario)}
      </time>
      <div className={styles.corpo}>
        <span className={styles.descricao}>
          {venda.quantidade}× {venda.prato_nome} · {venda.formato}
          {admin && <span className={styles.autor}> · {admin.autor}</span>}
        </span>
        {admin && (
          <span className={styles.valores}>
            {formatarMoeda(admin.preco_unitario)} · {formatarMoeda(admin.valor_total)}
          </span>
        )}
        {admin && venda.cancelada && (
          <span className={styles.motivo}>
            Cancelada por {admin.cancelada_por}
            {admin.cancelada_em && ` às ${formatarHorario(admin.cancelada_em)}`}
            {admin.motivo_cancelamento && ` · ${admin.motivo_cancelamento}`}
          </span>
        )}
      </div>
      <div className={styles.lado}>
        {venda.cancelada && <Etiqueta variante="cancelada" />}
        {admin && !venda.cancelada && aoCancelar && (
          <button className={styles.cancelar} type="button" onClick={aoCancelar}>
            Cancelar
          </button>
        )}
      </div>
    </li>
  );
}
