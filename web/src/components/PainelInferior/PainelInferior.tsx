"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import styles from "./PainelInferior.module.css";

const FOCAVEL = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Bottom sheet: prende o foco dentro do painel e devolve ao elemento de origem ao fechar.
// Fecha com Escape e com o botão Voltar.
export function PainelInferior({
  aberto,
  titulo,
  aoFechar,
  children,
}: {
  aberto: boolean;
  titulo: string;
  aoFechar: () => void;
  children: ReactNode;
}) {
  const tituloId = useId();
  const painelRef = useRef<HTMLDivElement>(null);
  const aoFecharRef = useRef(aoFechar);
  useEffect(() => {
    aoFecharRef.current = aoFechar;
  });

  useEffect(() => {
    if (!aberto) return;
    const origem = document.activeElement as HTMLElement | null;
    const painel = painelRef.current;
    const primeiro = painel?.querySelector<HTMLElement>(FOCAVEL);
    (primeiro ?? painel)?.focus();

    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === "Escape") {
        aoFecharRef.current();
        return;
      }
      if (evento.key !== "Tab" || !painel) return;
      const focaveis = Array.from(painel.querySelectorAll<HTMLElement>(FOCAVEL));
      if (focaveis.length === 0) return;
      const primeiroFocavel = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      if (evento.shiftKey && document.activeElement === primeiroFocavel) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primeiroFocavel.focus();
      }
    }

    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      origem?.focus();
    };
  }, [aberto]);

  if (!aberto) return null;

  return (
    <div className={styles.fundo}>
      <div
        ref={painelRef}
        className={styles.painel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        tabIndex={-1}
      >
        <h2 id={tituloId} className={styles.titulo}>
          {titulo}
        </h2>
        {children}
        <button className={styles.voltar} type="button" onClick={() => aoFecharRef.current()}>
          Voltar
        </button>
      </div>
    </div>
  );
}
