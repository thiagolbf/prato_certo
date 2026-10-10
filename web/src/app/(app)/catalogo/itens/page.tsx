"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { CampoFormulario } from "@/components/CampoFormulario/CampoFormulario";
import { DialogoConfirmacao } from "@/components/DialogoConfirmacao/DialogoConfirmacao";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { ListaCadastro, type ItemCadastro } from "@/components/ListaCadastro/ListaCadastro";
import { PainelInferior } from "@/components/PainelInferior/PainelInferior";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { ErroApi } from "@/lib/api";
import {
  alterarPreco,
  cadastrarItem,
  desativarItem,
  listarItens,
  listarPratos,
  reativarItem,
  type ItemDeCardapio,
  type Prato,
} from "@/lib/cadastro";
import type { Formato } from "@/lib/cardapio";
import { formatarMoeda } from "@/lib/formato";

import styles from "../catalogo.module.css";

type Estado =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "pronto"; itens: ItemDeCardapio[]; pratos: Prato[] };

// UI-11. Item é prato × formato com preço. Na edição só o preço muda: prato e formato são fixos (RN-03, RN-05).
export default function PaginaItens() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [mostrarDesativados, setMostrarDesativados] = useState(false);
  const [formularioAberto, setFormularioAberto] = useState(false);
  const [editando, setEditando] = useState<ItemDeCardapio | null>(null);
  const [paraDesativar, setParaDesativar] = useState<ItemDeCardapio | null>(null);
  const [pratoId, setPratoId] = useState("");
  const [formato, setFormato] = useState<Formato>("PF");
  const [preco, setPreco] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);

  useEffect(() => {
    let ativo = true;
    Promise.all([listarItens(), listarPratos()])
      .then(([itens, pratos]) => {
        if (ativo) setEstado({ tipo: "pronto", itens, pratos });
      })
      .catch(() => {
        if (ativo) setEstado({ tipo: "erro" });
      });
    return () => {
      ativo = false;
    };
  }, [tentativa]);

  function recarregar() {
    setEstado({ tipo: "carregando" });
    setTentativa((t) => t + 1);
  }

  function fechar() {
    setFormularioAberto(false);
    setEditando(null);
    setPratoId("");
    setFormato("PF");
    setPreco("");
    setErro(null);
  }

  function abrirEdicao(item: ItemCadastro, itens: ItemDeCardapio[]) {
    const original = itens.find((i) => i.id === item.id) ?? null;
    setEditando(original);
    setPreco(original ? original.preco : "");
    setErro(null);
    setFormularioAberto(true);
  }

  function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setProcessando(true);
    const operacao = editando
      ? alterarPreco(editando.id, preco)
      : cadastrarItem({ prato_id: Number(pratoId), formato, preco });
    operacao
      .then(() => {
        fechar();
        recarregar();
      })
      .catch((e: unknown) => setErro(e instanceof ErroApi && e.mensagem ? e.mensagem : "Não foi possível salvar agora."))
      .finally(() => setProcessando(false));
  }

  function confirmarDesativar() {
    if (!paraDesativar) return;
    setProcessando(true);
    desativarItem(paraDesativar.id)
      .then(() => {
        setParaDesativar(null);
        recarregar();
      })
      .catch((e: unknown) => setErro(e instanceof ErroApi && e.mensagem ? e.mensagem : "Não foi possível desativar agora."))
      .finally(() => setProcessando(false));
  }

  if (estado.tipo === "carregando") return <Skeleton linhas={4} />;
  if (estado.tipo === "erro") return <ErroCarregamento onTentarDeNovo={recarregar} />;

  const itensLista: ItemCadastro[] = estado.itens.map((i) => ({
    id: i.id,
    nome: `${i.prato_nome} · ${i.formato}`,
    ativo: i.ativo,
    detalhe: formatarMoeda(i.preco),
  }));
  const pratosAtivos = estado.pratos.filter((p) => p.ativo);

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Itens de cardápio</h1>
      <button className={styles.novo} type="button" onClick={() => setFormularioAberto(true)}>
        Novo item
      </button>

      <ListaCadastro
        itens={itensLista}
        mostrarDesativados={mostrarDesativados}
        aoMudarFiltro={setMostrarDesativados}
        aoEditar={(item) => abrirEdicao(item, estado.itens)}
        aoDesativar={(item) => setParaDesativar(estado.itens.find((i) => i.id === item.id) ?? null)}
        aoReativar={(item) => {
          reativarItem(item.id).then(recarregar);
        }}
      />

      <PainelInferior
        aberto={formularioAberto}
        titulo={editando ? `Preço de ${editando.prato_nome} · ${editando.formato}` : "Novo item"}
        aoFechar={fechar}
      >
        <form className={styles.formulario} onSubmit={salvar} noValidate>
          {!editando && (
            <>
              <label className={styles.rotulo} htmlFor="prato-item">
                Prato
              </label>
              <select id="prato-item" className={styles.seletor} value={pratoId} onChange={(e) => setPratoId(e.target.value)}>
                <option value="">Escolha o prato</option>
                {pratosAtivos.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome}
                  </option>
                ))}
              </select>
              <div role="radiogroup" aria-label="Formato" className={styles.formatos}>
                {(["PF", "MARMITA"] as Formato[]).map((f) => (
                  <button
                    key={f}
                    type="button"
                    role="radio"
                    aria-checked={formato === f}
                    className={styles.formato}
                    onClick={() => setFormato(f)}
                  >
                    {f === "PF" ? "PF" : "Marmita"}
                  </button>
                ))}
              </div>
            </>
          )}
          <CampoFormulario rotulo="Preço" inputMode="decimal" value={preco} onChange={(e) => setPreco(e.target.value)} />
          {editando && (
            <Aviso variante="informacao">As vendas anteriores continuam com o preço antigo.</Aviso>
          )}
          {erro && <Aviso variante="falha">{erro}</Aviso>}
          <button className={styles.novo} type="submit" disabled={processando}>
            Salvar
          </button>
        </form>
      </PainelInferior>

      <DialogoConfirmacao
        aberto={paraDesativar !== null}
        titulo="Desativar item?"
        consequencia="O item sai do cardápio e da tela de registro na hora."
        rotuloAcao="Desativar item"
        processando={processando}
        erro={erro ?? undefined}
        aoConfirmar={confirmarDesativar}
        aoFechar={() => setParaDesativar(null)}
      />
    </section>
  );
}
