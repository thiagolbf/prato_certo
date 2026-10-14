"use client";

import { useId, type InputHTMLAttributes } from "react";

import styles from "./CampoFormulario.module.css";

// Rótulo visível, erro junto ao campo e a descrição ligada ao campo para leitores de tela.
export function CampoFormulario({
  rotulo,
  erro,
  ...campo
}: { rotulo: string; erro?: string } & InputHTMLAttributes<HTMLInputElement>) {
  const idGerado = useId();
  const id = campo.id ?? idGerado;
  const idErro = `${id}-erro`;

  return (
    <div className={styles.campo}>
      <label className={styles.rotulo} htmlFor={id}>
        {rotulo}
      </label>
      <input
        {...campo}
        id={id}
        className={`${styles.entrada} ${erro ? styles.comErro : ""}`}
        aria-invalid={erro ? true : undefined}
        aria-describedby={erro ? idErro : undefined}
      />
      {erro && (
        <p id={idErro} className={styles.erro}>
          {erro}
        </p>
      )}
    </div>
  );
}
