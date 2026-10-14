"use client";

import { formatarDataCurta, formatarMoeda } from "@/lib/formato";
import type { QuebraDia } from "@/lib/fechamento";

import styles from "./QuebraPorDia.module.css";

// Tabela "Por dia" do fechamento do mês. Cada linha abre o fechamento daquele dia (RN-55).
export function QuebraPorDia({
  linhas,
  aoEscolherDia,
}: {
  linhas: QuebraDia[];
  aoEscolherDia: (dia: string) => void;
}) {
  if (linhas.length === 0) return <p className={styles.vazio}>Nenhuma venda neste mês.</p>;
  return (
    <table className={styles.tabela}>
      <thead>
        <tr>
          <th>Dia</th>
          <th>Unidades</th>
          <th>Faturamento</th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((linha) => (
          <tr key={linha.dia}>
            <td>
              <button className={styles.dia} type="button" onClick={() => aoEscolherDia(linha.dia)}>
                {formatarDataCurta(linha.dia)}
              </button>
            </td>
            <td>{linha.unidades}</td>
            <td>{formatarMoeda(linha.faturamento)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
