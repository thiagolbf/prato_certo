"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { AvisoCardapioHerdado } from "@/components/AvisoCardapioHerdado/AvisoCardapioHerdado";
import { AvisoFalhaEnvio } from "@/components/AvisoFalhaEnvio/AvisoFalhaEnvio";
import { DialogoConfirmacao } from "@/components/DialogoConfirmacao/DialogoConfirmacao";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { GradeCardapio } from "@/components/GradeCardapio/GradeCardapio";
import { PainelConfirmacao } from "@/components/PainelConfirmacao/PainelConfirmacao";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { Toast } from "@/components/Toast/Toast";
import { api, ErroApi, SessaoExpirada } from "@/lib/api";
import type { CardapioVigente, ItemCardapio } from "@/lib/cardapio";
import { formatarDataCurta } from "@/lib/formato";
import { conferirPendencias, lerPendencias, salvarPendencias, type Pendencia } from "@/lib/pendencias";
import { useSessao } from "@/lib/sessao";
import { gerarChave, registrarVenda } from "@/lib/vendas";

import styles from "./registrar.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; cardapio: CardapioVigente };

const TEMPO_DO_TOAST_MS = 3000;

// UI-02. Só busca o cardápio ao abrir e ao tocar "Atualizar" (SPEC-UI §7.2): não se atualiza sozinha.
export default function PaginaRegistrar() {
  const { login, perfil, diaOperacional } = useSessao();
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [itemEmConfirmacao, setItemEmConfirmacao] = useState<ItemCardapio | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [recusada, setRecusada] = useState(false);
  // Ao abrir a tela, cada pendência é conferida contra o usuário e o dia operacional do servidor (RN-56):
  // as de outro usuário ou de outro dia são descartadas sem enviar e avisadas uma vez.
  const [conferencia] = useState(() => conferirPendencias(lerPendencias(), login, diaOperacional));
  const [pendencias, setPendencias] = useState<Pendencia[]>(conferencia.validas);
  const [descartadas, setDescartadas] = useState<Pendencia[]>(conferencia.descartadas);
  const [sessaoExpirada, setSessaoExpirada] = useState(false);
  const [reenviando, setReenviando] = useState<string | null>(null);
  const [paraDescartar, setParaDescartar] = useState<Pendencia | null>(null);

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

  // Pendência em `sessionStorage` (RN-56): persistida a cada mudança da lista.
  useEffect(() => {
    salvarPendencias(pendencias);
  }, [pendencias]);

  // Com venda pendente, fechar a aba pede confirmação ao navegador.
  useEffect(() => {
    if (pendencias.length === 0) return;
    function aoSair(evento: BeforeUnloadEvent) {
      evento.preventDefault();
    }
    window.addEventListener("beforeunload", aoSair);
    return () => window.removeEventListener("beforeunload", aoSair);
  }, [pendencias.length]);

  function atualizar() {
    setRecusada(false);
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  // Grava na hora, sem esperar o efeito: o 401 leva ao login e a página pode ser descarregada antes dele.
  function guardar(pendencia: Pendencia) {
    setPendencias((atuais) => {
      const novas = [...atuais, pendencia];
      salvarPendencias(novas);
      return novas;
    });
  }

  function remover(chave: string) {
    setPendencias((atuais) => atuais.filter((p) => p.chave !== chave));
  }

  // Retorno otimista: o toast aparece antes da resposta, e a grade não espera o envio (RN-18, CA-01).
  // Falha de rede vira pendência (RN-56); recusa da API (422) não vira pendência, porque seria recusada de novo.
  function confirmar(item: ItemCardapio, quantidade: number) {
    const pendencia: Pendencia = {
      chave: gerarChave(),
      itemId: item.item_id,
      nomePrato: item.nome_prato,
      formato: item.formato,
      quantidade,
      usuario: login,
      diaOperacional,
    };
    setItemEmConfirmacao(null);
    setRecusada(false);
    setToast(`✓ Registrado: ${quantidade}× ${item.nome_prato} · ${item.formato}`);

    registrarVenda({ itemId: item.item_id, quantidade, chave: pendencia.chave }).catch(
      (erro: unknown) => {
        if (erro instanceof ErroApi && erro.status === 422) {
          setRecusada(true);
          return;
        }
        guardar(pendencia);
        if (erro instanceof SessaoExpirada) setSessaoExpirada(true);
      },
    );
  }

  // Reenvio usa a mesma chave: se a primeira chegou ao servidor, a segunda volta como 200 e não duplica.
  function reenviar(pendencia: Pendencia) {
    setReenviando(pendencia.chave);
    registrarVenda({
      itemId: pendencia.itemId,
      quantidade: pendencia.quantidade,
      chave: pendencia.chave,
    })
      .then(() => {
        remover(pendencia.chave);
        setToast(`✓ Registrado: ${pendencia.quantidade}× ${pendencia.nomePrato} · ${pendencia.formato}`);
      })
      .catch((erro: unknown) => {
        if (erro instanceof ErroApi && erro.status === 422) {
          remover(pendencia.chave);
          setRecusada(true);
        } else if (erro instanceof SessaoExpirada) {
          setSessaoExpirada(true);
        }
      })
      .finally(() => setReenviando(null));
  }

  function descartar(pendencia: Pendencia) {
    remover(pendencia.chave);
    setParaDescartar(null);
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

      {descartadas.length > 0 && (
        <Aviso variante="aviso">
          <p className={styles.avisoTitulo}>Uma venda pendente foi descartada sem ser registrada</p>
          <ul className={styles.descartadas}>
            {descartadas.map((d) => (
              <li key={d.chave}>
                {d.quantidade}× {d.nomePrato} · {d.formato} — ficou pendente em {formatarDataCurta(d.diaOperacional)}
                {d.usuario !== login ? ` (de ${d.usuario})` : ""}
              </li>
            ))}
          </ul>
          <p>Se ela aconteceu, avise o responsável.</p>
          <button className={styles.atualizar} type="button" onClick={() => setDescartadas([])}>
            Entendi
          </button>
        </Aviso>
      )}

      {sessaoExpirada && (
        <Aviso variante="falha">
          <p className={styles.avisoTitulo}>Sua sessão expirou. A venda NÃO foi registrada.</p>
          <p>Ela ficou pendente neste aparelho. Entre de novo com o mesmo usuário para reenviar.</p>
          <Link className={styles.acao} href="/login?motivo=sessao-expirada">
            Entrar novamente
          </Link>
        </Aviso>
      )}

      {pendencias.length > 0 && !sessaoExpirada && (
        <AvisoFalhaEnvio
          pendencias={pendencias}
          reenviando={reenviando}
          aoReenviar={reenviar}
          aoDescartar={setParaDescartar}
        />
      )}

      {recusada && (
        <Aviso variante="falha">
          <p className={styles.avisoTitulo}>Venda NÃO registrada</p>
          <p>O cardápio desta tela está desatualizado.</p>
          <button className={styles.atualizar} type="button" onClick={atualizar}>
            Atualizar cardápio
          </button>
        </Aviso>
      )}

      <div className={sessaoExpirada ? styles.desabilitada : undefined} inert={sessaoExpirada}>
        <GradeCardapio itens={cardapio.itens} aoTocar={setItemEmConfirmacao} />
      </div>

      <PainelConfirmacao
        item={itemEmConfirmacao}
        aoConfirmar={(quantidade) => {
          if (itemEmConfirmacao) confirmar(itemEmConfirmacao, quantidade);
        }}
        aoCancelar={() => setItemEmConfirmacao(null)}
      />

      <DialogoConfirmacao
        aberto={paraDescartar !== null}
        titulo="Descartar esta venda?"
        consequencia="Ela não será registrada e não entra no fechamento."
        rotuloAcao="Descartar venda"
        aoConfirmar={() => {
          if (paraDescartar) descartar(paraDescartar);
        }}
        aoFechar={() => setParaDescartar(null)}
      />

      {toast && (
        <div className={styles.flutuante}>
          <Toast>{toast}</Toast>
        </div>
      )}
    </section>
  );
}
