"use client";

import styles from "./NavegadorData.module.css";

export type Granularidade = "dia" | "mes";

// Datas trafegam como texto da API: `AAAA-MM-DD` para dia e `AAAA-MM` para mês.
// A aritmética é feita em UTC para não depender do fuso do aparelho.
function deslocar(valor: string, passo: 1 | -1, granularidade: Granularidade): string {
  if (granularidade === "mes") {
    const [ano, mes] = valor.split("-").map(Number);
    const data = new Date(Date.UTC(ano, mes - 1 + passo, 1));
    return `${data.getUTCFullYear()}-${String(data.getUTCMonth() + 1).padStart(2, "0")}`;
  }
  const [ano, mes, dia] = valor.split("-").map(Number);
  const data = new Date(Date.UTC(ano, mes - 1, dia + passo));
  return data.toISOString().slice(0, 10);
}

// ‹ data › com escolha direta. O "próximo" para no limite superior (hoje, em UI-05 e UI-07).
export function NavegadorData({
  valor,
  limiteSuperior,
  granularidade = "dia",
  aoMudar,
}: {
  valor: string;
  limiteSuperior?: string;
  granularidade?: Granularidade;
  aoMudar: (novoValor: string) => void;
}) {
  const noLimite = limiteSuperior !== undefined && valor >= limiteSuperior;
  const rotulo = granularidade === "mes" ? "Mês" : "Dia";

  return (
    <div className={styles.navegador}>
      <button
        className={styles.passo}
        type="button"
        aria-label={`${rotulo} anterior`}
        onClick={() => aoMudar(deslocar(valor, -1, granularidade))}
      >
        ‹
      </button>
      <input
        className={styles.escolha}
        type={granularidade === "mes" ? "month" : "date"}
        aria-label={`Escolher ${granularidade === "mes" ? "mês" : "data"}`}
        value={valor}
        max={limiteSuperior}
        onChange={(evento) => {
          if (evento.target.value) aoMudar(evento.target.value);
        }}
      />
      <button
        className={styles.passo}
        type="button"
        aria-label={`${rotulo} seguinte`}
        disabled={noLimite}
        onClick={() => aoMudar(deslocar(valor, 1, granularidade))}
      >
        ›
      </button>
    </div>
  );
}
