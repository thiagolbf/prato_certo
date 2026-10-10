"use client";

import { PainelInferior } from "@/components/PainelInferior/PainelInferior";

import styles from "./DialogoConfirmacao.module.css";

// Confirmação de ação destrutiva: a consequência em uma frase, a ação e Voltar.
export function DialogoConfirmacao({
  aberto,
  titulo,
  consequencia,
  rotuloAcao,
  processando = false,
  aoConfirmar,
  aoFechar,
}: {
  aberto: boolean;
  titulo: string;
  consequencia: string;
  rotuloAcao: string;
  processando?: boolean;
  aoConfirmar: () => void;
  aoFechar: () => void;
}) {
  return (
    <PainelInferior aberto={aberto} titulo={titulo} aoFechar={aoFechar}>
      <p className={styles.consequencia}>{consequencia}</p>
      <button
        className={styles.acao}
        type="button"
        disabled={processando}
        onClick={aoConfirmar}
      >
        {processando ? "Processando…" : rotuloAcao}
      </button>
    </PainelInferior>
  );
}
