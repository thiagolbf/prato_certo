"use client";

import { useState } from "react";

import { PainelInferior } from "@/components/PainelInferior/PainelInferior";

import styles from "./DialogoCancelarVenda.module.css";

export const LIMITE_MOTIVO = 200;

// Cancelamento de venda pelo ADMIN (UI-06). O motivo é obrigatório e não sai do diálogo sem ele (RN-26).
export function DialogoCancelarVenda({
  aberto,
  resumo,
  processando,
  erro,
  aoConfirmar,
  aoFechar,
}: {
  aberto: boolean;
  resumo: string;
  processando: boolean;
  erro: string | null;
  aoConfirmar: (motivo: string) => void;
  aoFechar: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  const [semMotivo, setSemMotivo] = useState(false);

  function confirmar() {
    if (!motivo.trim()) {
      setSemMotivo(true);
      return;
    }
    setSemMotivo(false);
    aoConfirmar(motivo.trim());
  }

  return (
    <PainelInferior aberto={aberto} titulo="Cancelar esta venda?" aoFechar={aoFechar}>
      <p className={styles.resumo}>{resumo}</p>
      <p className={styles.consequencia}>
        A venda sai dos totais e do fechamento. Ela continua na lista, marcada como cancelada.
      </p>
      <label className={styles.rotulo} htmlFor="motivo-cancelamento">
        Motivo
      </label>
      <textarea
        id="motivo-cancelamento"
        className={`${styles.campo} ${semMotivo ? styles.comErro : ""}`}
        maxLength={LIMITE_MOTIVO}
        rows={3}
        value={motivo}
        disabled={processando}
        aria-invalid={semMotivo || undefined}
        aria-describedby={semMotivo ? "motivo-erro" : undefined}
        onChange={(evento) => setMotivo(evento.target.value)}
      />
      {semMotivo && (
        <p id="motivo-erro" className={styles.erro}>
          Informe o motivo do cancelamento.
        </p>
      )}
      {erro && (
        <p className={styles.erro} role="alert">
          {erro}
        </p>
      )}
      <button className={styles.acao} type="button" disabled={processando} onClick={confirmar}>
        {processando ? "Cancelando…" : "Cancelar venda"}
      </button>
    </PainelInferior>
  );
}
