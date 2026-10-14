import styles from "./Skeleton.module.css";

// Linhas cinzas na forma do conteúdo; escondidas de leitores de tela, que anunciam o carregamento no pai.
export function Skeleton({ linhas = 3 }: { linhas?: number }) {
  return (
    <div className={styles.grupo} aria-hidden="true">
      {Array.from({ length: linhas }, (_, i) => (
        <span key={i} className={styles.linha} />
      ))}
    </div>
  );
}
