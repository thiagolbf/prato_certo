"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AvisoCardapioHerdado } from "@/components/AvisoCardapioHerdado/AvisoCardapioHerdado";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { GradeCardapio } from "@/components/GradeCardapio/GradeCardapio";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { api } from "@/lib/api";
import type { CardapioVigente } from "@/lib/cardapio";
import { formatarDataCurta } from "@/lib/formato";
import { useSessao } from "@/lib/sessao";

import styles from "./registrar.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; cardapio: CardapioVigente };

// UI-02. Só busca o cardápio ao abrir e ao tocar "Atualizar" (SPEC-UI §7.2): não se atualiza sozinha.
export default function PaginaRegistrar() {
  const { perfil } = useSessao();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    api
      .get<CardapioVigente>("/cardapio/vigente")
      .then((cardapio) => {
        if (ativo) setEstado({ tipo: "pronto", cardapio });
      })
      .catch(() => {
        if (ativo) setEstado({ tipo: "erro" });
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  function atualizar() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  if (estado.tipo === "carregando") return <Skeleton linhas={4} />;
  if (estado.tipo === "erro") return <ErroCarregamento onTentarDeNovo={atualizar} />;

  const { cardapio } = estado;
  if (cardapio.tipo === "VAZIO" || cardapio.itens.length === 0) {
    return perfil === "ADMIN" ? (
      <EstadoVazio titulo="Ainda não há cardápio para hoje.">
        <Link className={styles.acao} href="/cardapio">
          Montar cardápio
        </Link>
      </EstadoVazio>
    ) : (
      <EstadoVazio titulo="Chame o responsável para montar o cardápio do dia." />
    );
  }

  const herdado = cardapio.tipo === "HERDADO" && cardapio.data_origem !== null;

  return (
    <section className={styles.bloco}>
      <div className={styles.topo}>
        <h1 className={styles.titulo}>Cardápio de hoje · {formatarDataCurta(cardapio.data)}</h1>
        <button className={styles.atualizar} type="button" onClick={atualizar}>
          ↻ Atualizar
        </button>
      </div>
      {herdado && <p className={styles.marca}>Herdado de {formatarDataCurta(cardapio.data_origem!)}</p>}
      {herdado && perfil === "ADMIN" && <AvisoCardapioHerdado dataOrigem={cardapio.data_origem!} />}
      <GradeCardapio itens={cardapio.itens} />
    </section>
  );
}
