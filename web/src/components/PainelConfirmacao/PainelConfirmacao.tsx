"use client";

import { useState } from "react";

import { PainelInferior } from "@/components/PainelInferior/PainelInferior";
import { SeletorQuantidade } from "@/components/SeletorQuantidade/SeletorQuantidade";
import type { ItemCardapio } from "@/lib/cardapio";
import { formatarMoeda } from "@/lib/formato";

import styles from "./PainelConfirmacao.module.css";

// Segundo toque (UI-03): quantidade 1 por padrão, Confirmar fecha na hora e entrega a quantidade.
export function PainelConfirmacao({
  item,
  aoConfirmar,
  aoCancelar,
}: {
  item: ItemCardapio | null;
  aoConfirmar: (quantidade: number) => void;
  aoCancelar: () => void;
}) {
  const [quantidade, setQuantidade] = useState(1);
  const [ultimoItem, setUltimoItem] = useState<ItemCardapio | null>(item);

  // Cada item aberto começa em 1. Ajustar durante a renderização evita um efeito só para isso.
  if (item !== ultimoItem) {
    setUltimoItem(item);
    setQuantidade(1);
  }

  return (
    <PainelInferior aberto={item !== null} titulo="Confirmar venda" aoFechar={aoCancelar}>
      {item && (
        <div className={styles.corpo}>
          <p className={styles.nome}>
            {item.nome_prato} · {item.formato}
          </p>
          <p className={styles.preco}>{formatarMoeda(item.preco)} cada</p>
          <SeletorQuantidade valor={quantidade} aoMudar={setQuantidade} />
          <button className={styles.confirmar} type="button" onClick={() => aoConfirmar(quantidade)}>
            Confirmar
          </button>
          <button className={styles.cancelar} type="button" onClick={aoCancelar}>
            Cancelar
          </button>
        </div>
      )}
    </PainelInferior>
  );
}
