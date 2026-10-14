import styles from "./ErroCarregamento.module.css";

// Falha ao buscar dados: mensagem neutra, sem detalhe técnico (RN-48), e nova tentativa.
export function ErroCarregamento({ onTentarDeNovo }: { onTentarDeNovo: () => void }) {
  return (
    <div className={styles.bloco} role="alert">
      <p className={styles.mensagem}>Não foi possível carregar esta tela.</p>
      <button className={styles.tentar} type="button" onClick={onTentarDeNovo}>
        Tentar de novo
      </button>
    </div>
  );
}
