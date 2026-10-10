"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { NavegadorData } from "@/components/NavegadorData/NavegadorData";
import { QuebraPorDia } from "@/components/QuebraPorDia/QuebraPorDia";
import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";
import { SeletorPeriodo, type Periodo } from "@/components/SeletorPeriodo/SeletorPeriodo";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { buscarFechamentoDia, buscarFechamentoMes, type FechamentoDia, type FechamentoMes } from "@/lib/fechamento";
import { formatarGramas, formatarMoeda } from "@/lib/formato";
import { useSessao } from "@/lib/sessao";

import styles from "./fechamento.module.css";

type Dados = { tipo: "dia"; dados: FechamentoDia } | { tipo: "mes"; dados: FechamentoMes };

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "pronto"; dados: Dados };

// UI-07. Modo Dia (`/fechamento?data=`) e modo Mês (`/fechamento?mes=`), só ADMIN (RN-55).
// Os números vêm prontos da API (RN-29, RN-31): a tela só organiza, sem somar no cliente.
export default function PaginaFechamento() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <TelaFechamento />
    </RotaRestrita>
  );
}

function TelaFechamento() {
  const { diaOperacional } = useSessao();
  const [periodo, setPeriodo] = useState<Periodo>("dia");
  const [data, setData] = useState(diaOperacional);
  const [mes, setMes] = useState(diaOperacional.slice(0, 7));
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    const busca: Promise<Dados> =
      periodo === "dia"
        ? buscarFechamentoDia(data).then((dados) => ({ tipo: "dia", dados }))
        : buscarFechamentoMes(mes).then((dados) => ({ tipo: "mes", dados }));
    busca
      .then((dados) => {
        if (ativo) setEstado({ tipo: "pronto", dados });
      })
      .catch(() => {
        if (ativo) setEstado({ tipo: "erro" });
      });
    return () => {
      ativo = false;
    };
  }, [periodo, data, mes, tentativa]);

  function trocarPeriodo(novo: Periodo) {
    setEstado({ tipo: "carregando" });
    setPeriodo(novo);
  }

  function mudarNavegacao(novo: string) {
    setEstado({ tipo: "carregando" });
    if (periodo === "dia") setData(novo);
    else setMes(novo);
  }

  function abrirDia(dia: string) {
    setEstado({ tipo: "carregando" });
    setData(dia);
    setPeriodo("dia");
  }

  function recarregar() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  const parcial = estado.tipo === "pronto" && estado.dados.dados.parcial;

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>
        {periodo === "dia" ? "Fechamento do dia" : "Fechamento do mês"}
        {parcial ? " (parcial)" : ""}
      </h1>
      <SeletorPeriodo valor={periodo} aoMudar={trocarPeriodo} />
      <NavegadorData
        valor={periodo === "dia" ? data : mes}
        limiteSuperior={periodo === "dia" ? diaOperacional : diaOperacional.slice(0, 7)}
        granularidade={periodo === "dia" ? "dia" : "mes"}
        aoMudar={mudarNavegacao}
      />

      {estado.tipo === "carregando" && <Skeleton linhas={6} />}
      {estado.tipo === "erro" && <ErroCarregamento onTentarDeNovo={recarregar} />}
      {estado.tipo === "pronto" && <Resumo dados={estado.dados} aoEscolherDia={abrirDia} />}
    </section>
  );
}

function Resumo({ dados, aoEscolherDia }: { dados: Dados; aoEscolherDia: (dia: string) => void }) {
  const d = dados.dados;
  const faturamento = (formato: string) =>
    formatarMoeda(d.faturamento_por_formato.find((f) => f.formato === formato)?.valor ?? "0.00");

  return (
    <>
      {dados.tipo === "dia" &&
        dados.dados.cancelamentos_posteriores.map((c) => (
          <Aviso key={c.venda_id} variante="informacao">
            <span>
              Cancelamento posterior: {c.quantidade}× {c.prato_nome} · {formatarMoeda(c.valor_total)}, cancelada
              por {c.cancelada_por} · {c.motivo_cancelamento}.{" "}
            </span>
            <Link href={`/vendas?data=${dados.dados.data}`}>Ver vendas desta data</Link>
          </Aviso>
        ))}

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Faturamento</h2>
        <div className={styles.grade2}>
          <Metrica rotulo="PF" valor={faturamento("PF")} />
          <Metrica rotulo="Marmita" valor={faturamento("MARMITA")} />
        </div>
        <div className={styles.destaque}>
          <span>Total</span>
          <strong>{formatarMoeda(d.faturamento_total)}</strong>
        </div>
      </section>

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Unidades</h2>
        <p className={styles.totalUnidades}>{d.total_unidades} unidades no total</p>
        <Tabela
          cabecalho={["Prato", "PF", "Marm.", "Total"]}
          linhas={d.unidades_por_prato.map((p) => [
            p.prato_nome,
            celulaDoItem(d, p.prato_nome, "PF"),
            celulaDoItem(d, p.prato_nome, "MARMITA"),
            String(p.unidades),
          ])}
        />
      </section>

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Proteína consumida (estimada)</h2>
        <Tabela
          cabecalho={["Proteína", "Quantidade"]}
          linhas={d.proteina_por_tipo.map((p) => [p.proteina_nome, formatarGramas(p.gramas)])}
        />
      </section>

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Por item</h2>
        <Tabela
          cabecalho={["Item", "Unidades"]}
          linhas={d.unidades_por_item.map((i) => [`${i.prato_nome} · ${i.formato}`, String(i.unidades)])}
        />
      </section>

      {dados.tipo === "mes" && (
        <section className={styles.bloco2}>
          <h2 className={styles.subtitulo}>Por dia</h2>
          <QuebraPorDia linhas={dados.dados.quebra_por_dia} aoEscolherDia={aoEscolherDia} />
        </section>
      )}
    </>
  );
}

// Só organiza os números que a API já calculou: a célula recebe a unidade do item, sem somar.
function celulaDoItem(d: FechamentoDia | FechamentoMes, prato: string, formato: string): string {
  const item = d.unidades_por_item.find((i) => i.prato_nome === prato && i.formato === formato);
  return item ? String(item.unidades) : "—";
}

function Metrica({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className={styles.metrica}>
      <span>{rotulo}</span>
      <strong>{valor}</strong>
    </div>
  );
}

function Tabela({ cabecalho, linhas }: { cabecalho: string[]; linhas: string[][] }) {
  if (linhas.length === 0) return <p className={styles.vazio}>Nenhum item vendido neste período.</p>;
  return (
    <table className={styles.tabela}>
      <thead>
        <tr>
          {cabecalho.map((c) => (
            <th key={c}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((linha, i) => (
          <tr key={i}>
            {linha.map((celula, j) => (
              <td key={j}>{celula}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
