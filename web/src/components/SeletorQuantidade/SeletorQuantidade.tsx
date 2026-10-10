"use client";

import styles from "./SeletorQuantidade.module.css";

export const MINIMO = 1;
export const MAXIMO = 20;

// `−` e `+`, sem teclado: a faixa 1–20 não chega a digitar 21 (RN-14).
export function SeletorQuantidade({
  valor,
  aoMudar,
}: {
  valor: number;
  aoMudar: (novoValor: number) => void;
}) {
  const noMaximo = valor >= MAXIMO;
  return (
    <div className={styles.seletor}>
      <div className={styles.controles}>
        <button
          className={styles.passo}
          type="button"
          aria-label="Diminuir"
          disabled={valor <= MINIMO}
          onClick={() => aoMudar(valor - 1)}
        >
          −
        </button>
        <output className={styles.valor} aria-live="polite">
          {valor}
        </output>
        <button
          className={styles.passo}
          type="button"
          aria-label="Aumentar"
          disabled={noMaximo}
          onClick={() => aoMudar(valor + 1)}
        >
          +
        </button>
      </div>
      {valor > MINIMO && !noMaximo && (
        <p className={styles.unidades}>{valor} unidades</p>
      )}
      {noMaximo && (
        <p className={styles.limite}>
          Máximo de {MAXIMO} por lançamento. Para mais, confirme este e faça outro lançamento.
        </p>
      )}
    </div>
  );
}
