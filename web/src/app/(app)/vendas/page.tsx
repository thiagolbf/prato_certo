"use client";

import { useEffect, useState } from "react";

import { DialogoCancelarVenda } from "@/components/DialogoCancelarVenda/DialogoCancelarVenda";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { LinhaVenda } from "@/components/LinhaVenda/LinhaVenda";
import { NavegadorData } from "@/components/NavegadorData/NavegadorData";
import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { Toast } from "@/components/Toast/Toast";
import { ErroApi } from "@/lib/api";
import { formatarMoeda } from "@/lib/formato";
import { useSessao } from "@/lib/sessao";
import { cancelarVenda, listarVendasDaData, type VendaDaData, type VendasDaData } from "@/lib/vendas";

import styles from "./vendas.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; dados: VendasDaData };

// UI-05. Guarda por perfil: quem não é ADMIN nem monta a tela nem chama a API (ADR-009).
export default function VendasDaDataPagina() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <TelaVendasDaData />
    </RotaRestrita>
  );
}

function TelaVendasDaData() {
  const { diaOperacional } = useSessao();
  // A data vem da URL (`/vendas?data=`, usada pelo atalho do fechamento); sem ela, é hoje.
  const [data, setData] = useState(() => {
    if (typeof window === "undefined") return diaOperacional;
    const pedida = new URLSearchParams(window.location.search).get("data");
    return pedida && /^\d{4}-\d{2}-\d{2}$/.test(pedida) && pedida <= diaOperacional ? pedida : diaOperacional;
  });
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [alvo, setAlvo] = useState<VendaDaData | null>(null);
  const [processando, setProcessando] = useState(false);
  const [erroDialogo, setErroDialogo] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    listarVendasDaData(data)
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

  useEffect(() => {
    if (!toast) return;
    const temporizador = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(temporizador);
  }, [toast]);

  function mudarData(nova: string) {
    setEstado({ tipo: "carregando" });
    setData(nova);
  }

  function recarregar() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  function fecharDialogo() {
    setAlvo(null);
    setErroDialogo(null);
  }

  function confirmarCancelamento(motivo: string) {
    if (!alvo) return;
    setProcessando(true);
    setErroDialogo(null);
    cancelarVenda(alvo.id, motivo)
      .then(() => {
        fecharDialogo();
        setToast("Venda cancelada. Totais atualizados.");
        recarregar();
      })
      .catch((erro: unknown) => {
        if (erro instanceof ErroApi && erro.status === 409) {
          setErroDialogo("Esta venda já foi cancelada.");
          recarregar();
        } else {
          setErroDialogo("Não foi possível cancelar agora. Tente de novo.");
        }
      })
      .finally(() => setProcessando(false));
  }

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Vendas da data</h1>
      <NavegadorData valor={data} limiteSuperior={diaOperacional} aoMudar={mudarData} />

      {estado.tipo === "carregando" && <Skeleton linhas={4} />}
      {estado.tipo === "erro" && <ErroCarregamento onTentarDeNovo={recarregar} />}

      {estado.tipo === "pronto" && (
        <>
          <p className={styles.totais}>
            {estado.dados.total_unidades} unidades · {formatarMoeda(estado.dados.total_valor)}
          </p>
          {estado.dados.vendas.length === 0 ? (
            <EstadoVazio titulo="Nenhuma venda nesta data." />
          ) : (
            <ul className={styles.lista}>
              {[...estado.dados.vendas]
                .sort((a, b) => b.horario.localeCompare(a.horario))
                .map((venda) => (
                  <LinhaVenda
                    key={venda.id}
                    venda={venda}
                    aoCancelar={() => {
                      setErroDialogo(null);
                      setAlvo(venda);
                    }}
                  />
                ))}
            </ul>
          )}
        </>
      )}

      <DialogoCancelarVenda
        aberto={alvo !== null}
        resumo={alvo ? `${alvo.quantidade}× ${alvo.prato_nome} · ${alvo.formato} · ${alvo.autor}` : ""}
        processando={processando}
        erro={erroDialogo}
        aoConfirmar={confirmarCancelamento}
        aoFechar={fecharDialogo}
      />

      {toast && (
        <div className={styles.flutuante}>
          <Toast>{toast}</Toast>
        </div>
      )}
    </section>
  );
}
