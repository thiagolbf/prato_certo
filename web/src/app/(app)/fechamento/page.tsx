"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { NavegadorData } from "@/components/NavegadorData/NavegadorData";
import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { formatarGramas, formatarMoeda } from "@/lib/formato";
import { buscarFechamentoDia, type FechamentoDia } from "@/lib/fechamento";
import { useSessao } from "@/lib/sessao";

import styles from "./fechamento.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; dados: FechamentoDia };

// UI-07, modo Dia. Só ADMIN; os números vêm prontos da API (RN-29, RN-31), sem somar no cliente.
export default function PaginaFechamento() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <TelaFechamentoDia />
    </RotaRestrita>
  );
}

function TelaFechamentoDia() {
  const { diaOperacional } = useSessao();
  const [data, setData] = useState(diaOperacional);
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let ativo = true;
    buscarFechamentoDia(data)
      .then((dados) => {
        if (ativo) setEstado({ tipo: "pronto", dados });
      })
      .catch(() => {
        if (ativo) setEstado({ tipo: "erro" });
      });
    return () => {
      ativo = false;
    };
  }, [data, tentativa]);

  function mudarData(nova: string) {
    setEstado({ tipo: "carregando" });
    setData(nova);
  }

  function recarregar() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>
        Fechamento do dia{estado.tipo === "pronto" && estado.dados.parcial ? " (parcial)" : ""}
      </h1>
      <NavegadorData valor={data} limiteSuperior={diaOperacional} aoMudar={mudarData} />

      {estado.tipo === "carregando" && <Skeleton linhas={6} />}
      {estado.tipo === "erro" && <ErroCarregamento onTentarDeNovo={recarregar} />}
      {estado.tipo === "pronto" && <Resumo dados={estado.dados} />}
    </section>
  );
}

function Resumo({ dados }: { dados: FechamentoDia }) {
  const faturamento = (formato: string) =>
    formatarMoeda(dados.faturamento_por_formato.find((f) => f.formato === formato)?.valor ?? "0.00");

  return (
    <>
      {dados.cancelamentos_posteriores.map((c) => (
        <Aviso key={c.venda_id} variante="informacao">
          <span>
            Cancelamento posterior: {c.quantidade}× {c.prato_nome} · {formatarMoeda(c.valor_total)}, cancelada
            por {c.cancelada_por} · {c.motivo_cancelamento}.{" "}
          </span>
          <Link href={`/vendas?data=${dados.data}`}>Ver vendas desta data</Link>
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
          <strong>{formatarMoeda(dados.faturamento_total)}</strong>
        </div>
      </section>

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Unidades</h2>
        <p className={styles.totalUnidades}>{dados.total_unidades} unidades no total</p>
        <Tabela
          cabecalho={["Prato", "PF", "Marm.", "Total"]}
          linhas={dados.unidades_por_prato.map((p) => [
            p.prato_nome,
            celulaDoItem(dados, p.prato_nome, "PF"),
            celulaDoItem(dados, p.prato_nome, "MARMITA"),
            String(p.unidades),
          ])}
        />
      </section>

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Proteína consumida (estimada)</h2>
        <Tabela
          cabecalho={["Proteína", "Quantidade"]}
          linhas={dados.proteina_por_tipo.map((p) => [p.proteina_nome, formatarGramas(p.gramas)])}
        />
      </section>

      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Por item</h2>
        <Tabela
          cabecalho={["Item", "Unidades"]}
          linhas={dados.unidades_por_item.map((i) => [
            `${i.prato_nome} · ${i.formato}`,
            String(i.unidades),
          ])}
        />
      </section>
    </>
  );
}

// Só organiza os números que a API já calculou: a célula recebe a unidade do item, sem somar.
function celulaDoItem(dados: FechamentoDia, prato: string, formato: string): string {
  const item = dados.unidades_por_item.find((i) => i.prato_nome === prato && i.formato === formato);
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
  if (linhas.length === 0) return <p className={styles.vazio}>Nenhum item vendido nesta data.</p>;
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
