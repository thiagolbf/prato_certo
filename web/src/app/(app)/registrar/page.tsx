"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { AvisoCardapioHerdado } from "@/components/AvisoCardapioHerdado/AvisoCardapioHerdado";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { GradeCardapio } from "@/components/GradeCardapio/GradeCardapio";
import { PainelConfirmacao } from "@/components/PainelConfirmacao/PainelConfirmacao";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { Toast } from "@/components/Toast/Toast";
import { api, ErroApi } from "@/lib/api";
import type { CardapioVigente, ItemCardapio } from "@/lib/cardapio";
import { formatarDataCurta } from "@/lib/formato";
import { useSessao } from "@/lib/sessao";
import { gerarChave, registrarVenda } from "@/lib/vendas";

import styles from "./registrar.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; cardapio: CardapioVigente };

type Falha = { tipo: "recusado" } | { tipo: "semConexao" };

const TEMPO_DO_TOAST_MS = 3000;

// UI-02. Só busca o cardápio ao abrir e ao tocar "Atualizar" (SPEC-UI §7.2): não se atualiza sozinha.
export default function PaginaRegistrar() {
  const { perfil } = useSessao();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [itemEmConfirmacao, setItemEmConfirmacao] = useState<ItemCardapio | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [falha, setFalha] = useState<Falha | null>(null);

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

  useEffect(() => {
    if (!toast) return;
    const temporizador = setTimeout(() => setToast(null), TEMPO_DO_TOAST_MS);
    return () => clearTimeout(temporizador);
  }, [toast]);

  function atualizar() {
    setFalha(null);
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  // Retorno otimista: o toast aparece antes da resposta, e a grade não espera o envio (RN-18, CA-01).
  function confirmar(item: ItemCardapio, quantidade: number) {
    const chave = gerarChave();
    setItemEmConfirmacao(null);
    setFalha(null);
    setToast(`✓ Registrado: ${quantidade}× ${item.nome_prato} · ${item.formato}`);

    registrarVenda({ itemId: item.item_id, quantidade, chave }).catch((erro: unknown) => {
      // 422: o item saiu do cardápio ou a quantidade é inválida. Reenviar não resolveria (sem Reenviar).
      if (erro instanceof ErroApi && erro.status === 422) setFalha({ tipo: "recusado" });
      else setFalha({ tipo: "semConexao" });
    });
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

      {falha?.tipo === "recusado" && (
        <Aviso variante="falha">
          <p className={styles.avisoTitulo}>Venda NÃO registrada</p>
          <p>O cardápio desta tela está desatualizado.</p>
          <button className={styles.atualizar} type="button" onClick={atualizar}>
            Atualizar cardápio
          </button>
        </Aviso>
      )}
      {falha?.tipo === "semConexao" && (
        <Aviso variante="falha">
          <p className={styles.avisoTitulo}>Venda NÃO registrada — sem conexão</p>
        </Aviso>
      )}

      <GradeCardapio itens={cardapio.itens} aoTocar={setItemEmConfirmacao} />

      <PainelConfirmacao
        item={itemEmConfirmacao}
        aoConfirmar={(quantidade) => {
          if (itemEmConfirmacao) confirmar(itemEmConfirmacao, quantidade);
        }}
        aoCancelar={() => setItemEmConfirmacao(null)}
      />

      {toast && (
        <div className={styles.flutuante}>
          <Toast>{toast}</Toast>
        </div>
      )}
    </section>
  );
}
