"use client";

import { formatarMoeda } from "@/lib/formato";
import type { Formato, ItemCardapio } from "@/lib/cardapio";

import styles from "./GradeCardapio.module.css";

// Uma linha por prato, em ordem alfabética; PF à esquerda e Marmita à direita, célula vaga quando
// o formato não existe. Cada botão é um item de cardápio (prato × formato) e mostra o preço unitário.
export function GradeCardapio({
  itens,
  aoTocar,
}: {
  itens: ItemCardapio[];
  aoTocar?: (item: ItemCardapio) => void;
}) {
  const pratos = new Map<string, Partial<Record<Formato, ItemCardapio>>>();
  for (const item of itens) {
    const linha = pratos.get(item.nome_prato) ?? {};
    linha[item.formato] = item;
    pratos.set(item.nome_prato, linha);
  }
  const nomes = [...pratos.keys()].sort((a, b) => a.localeCompare(b, "pt-BR"));

  return (
    <div className={styles.grade} role="table" aria-label="Pratos do dia">
      <div className={styles.cabecalho} role="row">
        <span role="columnheader">Prato</span>
        <span role="columnheader">PF</span>
        <span role="columnheader">Marmita</span>
      </div>
      {nomes.map((nome) => {
        const linha = pratos.get(nome) ?? {};
        return (
          <div className={styles.linha} role="row" key={nome}>
            <span className={styles.prato} role="rowheader">
              {nome}
            </span>
            <Celula item={linha.PF} rotulo="PF" aoTocar={aoTocar} />
            <Celula item={linha.MARMITA} rotulo="Marmita" aoTocar={aoTocar} />
          </div>
        );
      })}
    </div>
  );
}

function Celula({
  item,
  rotulo,
  aoTocar,
}: {
  item: ItemCardapio | undefined;
  rotulo: string;
  aoTocar?: (item: ItemCardapio) => void;
}) {
  if (!item) return <span className={styles.vaga} role="cell" aria-label={`${rotulo} indisponível`} />;
  return (
    <span role="cell">
      <button className={styles.item} type="button" onClick={() => aoTocar?.(item)}>
        <span className={styles.formato}>{rotulo}</span>
        <span className={styles.preco}>{formatarMoeda(item.preco)}</span>
      </button>
    </span>
  );
}
