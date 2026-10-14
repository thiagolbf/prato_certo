"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { LinhaVenda } from "@/components/LinhaVenda/LinhaVenda";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { listarMinhasVendas, type VendaDoDia } from "@/lib/vendas";

import styles from "./minhas-vendas.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; vendas: VendaDoDia[] };

// UI-04. Lista das próprias vendas do dia, sem preço nem valor (RN-40). Nenhuma ação de cancelar (RN-21).
export default function PaginaMinhasVendas() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    listarMinhasVendas()
      .then((vendas) => {
        if (ativo) setEstado({ tipo: "pronto", vendas });
      })
      .catch(() => {
        if (ativo) setEstado({ tipo: "erro" });
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  function tentarDeNovo() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  if (estado.tipo === "carregando") return <Skeleton linhas={4} />;
  if (estado.tipo === "erro") return <ErroCarregamento onTentarDeNovo={tentarDeNovo} />;

  const { vendas } = estado;
  if (vendas.length === 0) {
    return (
      <EstadoVazio titulo="Nenhuma venda sua hoje.">
        <Link className={styles.acao} href="/registrar">
          Registrar venda
        </Link>
      </EstadoVazio>
    );
  }

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>
        Minhas vendas de hoje · {vendas.length} {vendas.length === 1 ? "lançamento" : "lançamentos"}
      </h1>
      <ul className={styles.lista}>
        {[...vendas]
          .sort((a, b) => b.horario.localeCompare(a.horario))
          .map((venda) => (
            <LinhaVenda key={venda.id} venda={venda} />
          ))}
      </ul>
      <p className={styles.rodape}>
        Lançou errado? Chame o responsável e aponte a venda nesta lista.
      </p>
    </section>
  );
}
