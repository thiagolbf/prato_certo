"use client";

import type { Pendencia } from "@/lib/pendencias";

import styles from "./AvisoFalhaEnvio.module.css";

// Vendas que não chegaram ao servidor. Cada uma tem Reenviar (mesma chave) e Descartar (com confirmação
// feita pela tela). Fica na tela até ser tratada: é `role="alert"`.
export function AvisoFalhaEnvio({
  pendencias,
  reenviando,
  aoReenviar,
  aoDescartar,
}: {
  pendencias: Pendencia[];
  reenviando: string | null;
  aoReenviar: (pendencia: Pendencia) => void;
  aoDescartar: (pendencia: Pendencia) => void;
}) {
  return (
    <div className={styles.aviso} role="alert">
      <p className={styles.titulo}>Venda NÃO registrada — sem conexão</p>
      <p className={styles.instrucao}>Não feche esta aba enquanto houver venda pendente.</p>
      <ul className={styles.lista}>
        {pendencias.map((pendencia) => {
          const enviando = reenviando === pendencia.chave;
          return (
            <li className={styles.item} key={pendencia.chave}>
              <span className={styles.descricao}>
                {pendencia.quantidade}× {pendencia.nomePrato} · {pendencia.formato}
              </span>
              <div className={styles.acoes}>
                <button
                  className={styles.reenviar}
                  type="button"
                  disabled={reenviando !== null}
                  onClick={() => aoReenviar(pendencia)}
                >
                  {enviando ? "Reenviando…" : "Reenviar"}
                </button>
                <button
                  className={styles.descartar}
                  type="button"
                  disabled={reenviando !== null}
                  onClick={() => aoDescartar(pendencia)}
                >
                  Descartar
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
