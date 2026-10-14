"use client";

import { useEffect, useState } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { Etiqueta } from "@/components/Etiqueta/Etiqueta";
import { NavegadorData } from "@/components/NavegadorData/NavegadorData";
import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { Toast } from "@/components/Toast/Toast";
import { api, ErroApi } from "@/lib/api";
import type { CardapioDaData, ItemDoCatalogo } from "@/lib/cardapio";
import { formatarDataCurta, formatarMoeda } from "@/lib/formato";
import { useSessao } from "@/lib/sessao";

import styles from "./cardapio.module.css";

type Dados = { cardapio: CardapioDaData; catalogo: ItemDoCatalogo[]; vendasHoje: number };
type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "pronto"; dados: Dados };
type Modo = "visualizar" | "editando";

const MENSAGEM_VALIDACAO = "Selecione pelo menos um item. Um cardápio não pode ficar vazio.";
const MENSAGEM_SUCESSO =
  "Cardápio salvo. Avise o balcão: ele aparece quando a tela de registro for atualizada.";

// UI-08. Cardápio de uma data: o de hoje e os futuros são editáveis; data passada é só leitura (RN-50).
export default function PaginaCardapio() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <TelaCardapio />
    </RotaRestrita>
  );
}

function TelaCardapio() {
  const { diaOperacional } = useSessao();
  const [data, setData] = useState(diaOperacional);
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [modo, setModo] = useState<Modo>("visualizar");
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [validacao, setValidacao] = useState<string | null>(null);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    Promise.all([
      api.get<CardapioDaData>(`/cardapio?data=${data}`),
      api.get<ItemDoCatalogo[]>("/itens"),
      data === diaOperacional
        ? api.get<{ vendas: unknown[] }>(`/vendas?data=${data}`).then((v) => v.vendas.length)
        : Promise.resolve(0),
    ])
      .then(([cardapio, catalogo, vendasHoje]) => {
        if (ativo) setEstado({ tipo: "pronto", dados: { cardapio, catalogo, vendasHoje } });
      })
      .catch(() => {
        if (ativo) setEstado({ tipo: "erro" });
      });
    return () => {
      ativo = false;
    };
  }, [data, tentativa, diaOperacional]);

  useEffect(() => {
    if (!toast) return;
    const temporizador = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(temporizador);
  }, [toast]);

  function recarregar() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  function mudarData(nova: string) {
    setModo("visualizar");
    setValidacao(null);
    setErroEnvio(null);
    setEstado({ tipo: "carregando" });
    setData(nova);
  }

  function editar(dados: Dados) {
    setSelecionados(dados.cardapio.itens.map((i) => i.item_id));
    setValidacao(null);
    setErroEnvio(null);
    setModo("editando");
  }

  // Grava a seleção (salvar, confirmar herdado). Vazio não sai daqui (CA-61).
  function gravar(itens: number[]) {
    if (itens.length === 0) {
      setValidacao(MENSAGEM_VALIDACAO);
      return;
    }
    setValidacao(null);
    setErroEnvio(null);
    setSalvando(true);
    api
      .post(`/cardapio/${data}`, { itens })
      .then(() => {
        setModo("visualizar");
        setToast(MENSAGEM_SUCESSO);
        recarregar();
      })
      .catch((erro: unknown) => {
        // A seleção fica como estava: o ADMIN tenta de novo sem refazer a lista.
        // Só a mensagem de negócio (4xx) chega ao ADMIN; falha de servidor vira texto neutro (RN-48).
        const negocio = erro instanceof ErroApi && erro.status < 500 ? erro.mensagem : undefined;
        setErroEnvio(negocio ?? "Não foi possível salvar agora. Tente de novo.");
      })
      .finally(() => setSalvando(false));
  }

  function alternar(itemId: number) {
    setSelecionados((atuais) =>
      atuais.includes(itemId) ? atuais.filter((id) => id !== itemId) : [...atuais, itemId],
    );
  }

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Cardápio da data</h1>
      <NavegadorData valor={data} aoMudar={mudarData} />

      {estado.tipo === "carregando" && <Skeleton linhas={5} />}
      {estado.tipo === "erro" && <ErroCarregamento onTentarDeNovo={recarregar} />}
      {estado.tipo === "pronto" && (
        <Conteudo
          dados={estado.dados}
          data={data}
          hoje={diaOperacional}
          modo={modo}
          selecionados={selecionados}
          validacao={validacao}
          erroEnvio={erroEnvio}
          salvando={salvando}
          aoEditar={() => editar(estado.dados)}
          aoAlternar={alternar}
          aoSalvar={() => gravar(selecionados)}
          aoConfirmarHerdado={() => gravar(estado.dados.cardapio.itens.map((i) => i.item_id))}
          aoDescartar={() => setModo("visualizar")}
          aoMontar={() => editar(estado.dados)}
        />
      )}

      {toast && (
        <div className={styles.flutuante}>
          <Toast>{toast}</Toast>
        </div>
      )}
    </section>
  );
}

function Conteudo(props: {
  dados: Dados;
  data: string;
  hoje: string;
  modo: Modo;
  selecionados: number[];
  validacao: string | null;
  erroEnvio: string | null;
  salvando: boolean;
  aoEditar: () => void;
  aoAlternar: (id: number) => void;
  aoSalvar: () => void;
  aoConfirmarHerdado: () => void;
  aoDescartar: () => void;
  aoMontar: () => void;
}) {
  const { dados, data, hoje, modo } = props;
  const { cardapio, catalogo, vendasHoje } = dados;
  const passada = cardapio.passada;

  if (modo === "editando") {
    const ativos = catalogo.filter((i) => i.ativo);
    return (
      <section className={styles.bloco2}>
        <h2 className={styles.subtitulo}>Editar cardápio de {formatarDataCurta(data)}</h2>
        <p className={styles.contador}>{props.selecionados.length} selecionados</p>
        {data === hoje && vendasHoje > 0 && (
          <Aviso variante="aviso">As vendas já registradas hoje ({vendasHoje}) não mudam.</Aviso>
        )}
        <ul className={styles.lista}>
          {ativos.map((item) => (
            <li className={styles.item} key={item.id}>
              <label className={styles.linha}>
                <input
                  type="checkbox"
                  checked={props.selecionados.includes(item.id)}
                  disabled={props.salvando}
                  onChange={() => props.aoAlternar(item.id)}
                />
                <span className={styles.nome}>
                  {item.prato_nome} · {item.formato}
                </span>
                <span className={styles.preco}>{formatarMoeda(item.preco)}</span>
              </label>
            </li>
          ))}
        </ul>
        {props.validacao && <Aviso variante="falha">{props.validacao}</Aviso>}
        {props.erroEnvio && <Aviso variante="falha">{props.erroEnvio}</Aviso>}
        <div className={styles.acoes}>
          <button className={styles.primario} type="button" disabled={props.salvando} onClick={props.aoSalvar}>
            {props.salvando ? "Salvando…" : "Salvar"}
          </button>
          <button className={styles.secundario} type="button" disabled={props.salvando} onClick={props.aoDescartar}>
            Descartar
          </button>
        </div>
      </section>
    );
  }

  if (cardapio.tipo === "VAZIO" || cardapio.itens.length === 0) {
    if (passada) {
      return <EstadoVazio titulo="Nenhum cardápio nesta data." />;
    }
    const futuro = data > hoje;
    return (
      <EstadoVazio
        titulo={
          futuro
            ? "Se nada for montado, nesse dia vale o cardápio mais recente anterior, como herdado."
            : "Os operadores não conseguem registrar vendas até você montar o primeiro."
        }
      >
        <button className={styles.primario} type="button" onClick={props.aoMontar}>
          Montar cardápio
        </button>
      </EstadoVazio>
    );
  }

  return (
    <section className={styles.bloco2}>
      {cardapio.tipo === "HERDADO" && cardapio.data_origem && (
        <Aviso variante="aviso">
          Herdado de {formatarDataCurta(cardapio.data_origem)} — ainda não confirmado.
        </Aviso>
      )}
      <div className={styles.topo}>
        <h2 className={styles.subtitulo}>Cardápio de {formatarDataCurta(data)}</h2>
        {cardapio.tipo === "PROPRIO" && <Etiqueta variante="proprio" />}
        {cardapio.tipo === "HERDADO" && <Etiqueta variante="herdado" />}
        {passada && <Etiqueta variante="somenteLeitura" />}
      </div>
      <ul className={styles.lista}>
        {cardapio.itens.map((item) => (
          <li className={styles.item} key={item.item_id}>
            <span className={styles.nome}>
              {item.nome_prato} · {item.formato}
            </span>
            <span className={styles.preco}>{formatarMoeda(item.preco)}</span>
          </li>
        ))}
      </ul>
      {props.erroEnvio && <Aviso variante="falha">{props.erroEnvio}</Aviso>}
      {!passada && (
        <div className={styles.acoes}>
          {cardapio.tipo === "HERDADO" && (
            <button className={styles.primario} type="button" disabled={props.salvando} onClick={props.aoConfirmarHerdado}>
              Confirmar este cardápio
            </button>
          )}
          <button className={styles.secundario} type="button" onClick={props.aoEditar}>
            {cardapio.tipo === "HERDADO" ? "Editar antes de confirmar" : "Editar cardápio"}
          </button>
        </div>
      )}
    </section>
  );
}
