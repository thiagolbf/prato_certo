import styles from "./Etiqueta.module.css";

export type VarianteEtiqueta = "cancelada" | "desativado" | "herdado" | "proprio" | "somenteLeitura";

const ROTULO: Record<VarianteEtiqueta, string> = {
  cancelada: "Cancelada",
  desativado: "Desativado",
  herdado: "Herdado",
  proprio: "Próprio",
  somenteLeitura: "Somente leitura",
};

// Pílula de estado. A cor vem das variáveis de `globals.css`; o texto sempre acompanha.
export function Etiqueta({ variante }: { variante: VarianteEtiqueta }) {
  return <span className={`${styles.etiqueta} ${styles[variante]}`}>{ROTULO[variante]}</span>;
}
