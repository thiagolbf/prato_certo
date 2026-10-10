"use client";

import styles from "./SeletorPeriodo.module.css";

export type Periodo = "dia" | "mes";

// Controle segmentado Dia | Mês (RN-55, UI-07).
export function SeletorPeriodo({
  valor,
  aoMudar,
}: {
  valor: Periodo;
  aoMudar: (periodo: Periodo) => void;
}) {
  const opcoes: { valor: Periodo; rotulo: string }[] = [
    { valor: "dia", rotulo: "Dia" },
    { valor: "mes", rotulo: "Mês" },
  ];

  return (
    <div className={styles.segmentos} role="group" aria-label="Período">
      {opcoes.map((opcao) => (
        <button
          key={opcao.valor}
          className={styles.segmento}
          type="button"
          aria-pressed={valor === opcao.valor}
          onClick={() => aoMudar(opcao.valor)}
        >
          {opcao.rotulo}
        </button>
      ))}
    </div>
  );
}
