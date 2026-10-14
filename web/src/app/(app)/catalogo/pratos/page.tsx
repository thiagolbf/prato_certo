"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { CampoFormulario } from "@/components/CampoFormulario/CampoFormulario";
import { DialogoConfirmacao } from "@/components/DialogoConfirmacao/DialogoConfirmacao";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { ListaCadastro, type ItemCadastro } from "@/components/ListaCadastro/ListaCadastro";
import { PainelInferior } from "@/components/PainelInferior/PainelInferior";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { alterarGramagem, cadastrarPrato, desativarPrato, listarPratos, reativarPrato, type Prato } from "@/lib/cadastro";
import { ErroApi } from "@/lib/api";
import { listarProteinas, type Proteina } from "@/lib/proteinas";

import styles from "../catalogo.module.css";

const normalizar = (texto: string) => texto.trim().toLocaleLowerCase("pt-BR");

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "pronto"; pratos: Prato[]; proteinas: Proteina[] };

// UI-10. Pratos com a mesma gramagem para PF e marmita (RN-02, RN-05). Editar a gramagem não muda vendas passadas.
export default function PaginaPratos() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [mostrarDesativados, setMostrarDesativados] = useState(false);
  const [formularioAberto, setFormularioAberto] = useState(false);
  const [editando, setEditando] = useState<Prato | null>(null);
  const [paraDesativar, setParaDesativar] = useState<Prato | null>(null);
  const [nome, setNome] = useState("");
  const [proteinaId, setProteinaId] = useState("");
  const [gramas, setGramas] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);
  const [desativadoRepetido, setDesativadoRepetido] = useState<Prato | null>(null);

  useEffect(() => {
    let ativo = true;
    Promise.all([listarPratos(), listarProteinas()])
      .then(([pratos, proteinas]) => {
        if (ativo) setEstado({ tipo: "pronto", pratos, proteinas });
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
    setNome("");
    setProteinaId("");
    setGramas("");
    setErro(null);
    setDesativadoRepetido(null);
  }

  function reativarRepetido(prato: Prato) {
    setProcessando(true);
    reativarPrato(prato.id)
      .then(() => {
        fechar();
        recarregar();
      })
      .catch(() => setErro("Não foi possível reativar agora."))
      .finally(() => setProcessando(false));
  }

  function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const valorGramas = Number(gramas);
    if (!Number.isInteger(valorGramas) || valorGramas <= 0) {
      setErro("Informe a gramagem em gramas, maior que zero.");
      return;
    }
    if (estado.tipo === "pronto" && !editando) {
      const repetido = estado.pratos.find((p) => normalizar(p.nome) === normalizar(nome));
      if (repetido?.ativo) {
        setErro("Já existe um prato com esse nome.");
        return;
      }
      if (repetido) {
        setDesativadoRepetido(repetido);
        setErro(null);
        return;
      }
    }
    setProcessando(true);
    const operacao = editando
      ? alterarGramagem(editando.id, valorGramas)
      : cadastrarPrato({ nome: nome.trim(), proteina_id: Number(proteinaId), gramas_por_porcao: valorGramas });
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
    desativarPrato(paraDesativar.id)
      .then(() => {
        setParaDesativar(null);
        recarregar();
      })
      .catch((e: unknown) => setErro(e instanceof ErroApi && e.mensagem ? e.mensagem : "Não foi possível desativar agora."))
      .finally(() => setProcessando(false));
  }

  if (estado.tipo === "carregando") return <Skeleton linhas={4} />;
  if (estado.tipo === "erro") return <ErroCarregamento onTentarDeNovo={recarregar} />;

  const itens: ItemCadastro[] = estado.pratos.map((p) => ({
    id: p.id,
    nome: p.nome,
    ativo: p.ativo,
    detalhe: `${p.proteina_nome} · ${p.gramas_por_porcao} g · ${p.itens_ativos} ${p.itens_ativos === 1 ? "item ativo" : "itens ativos"}`,
  }));
  const proteinasAtivas = estado.proteinas.filter((p) => p.ativo);
  const editar = (item: ItemCadastro) => {
    const prato = estado.pratos.find((p) => p.id === item.id) ?? null;
    setEditando(prato);
    setGramas(prato ? String(prato.gramas_por_porcao) : "");
    setErro(null);
    setFormularioAberto(true);
  };

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Pratos</h1>
      <button className={styles.novo} type="button" onClick={() => setFormularioAberto(true)}>
        Novo prato
      </button>

      {estado.pratos.length === 0 && <EstadoVazio titulo="Nenhum prato cadastrado." />}
      <ListaCadastro
        itens={itens}
        mostrarDesativados={mostrarDesativados}
        aoMudarFiltro={setMostrarDesativados}
        aoEditar={editar}
        aoDesativar={(item) => setParaDesativar(estado.pratos.find((p) => p.id === item.id) ?? null)}
        aoReativar={(item) => {
          reativarPrato(item.id).then(recarregar);
        }}
      />

      <PainelInferior
        aberto={formularioAberto}
        titulo={editando ? `Gramagem de ${editando.nome}` : "Novo prato"}
        aoFechar={fechar}
      >
        <form className={styles.formulario} onSubmit={salvar} noValidate>
          {!editando && (
            <>
              <CampoFormulario rotulo="Nome" value={nome} onChange={(e) => setNome(e.target.value)} />
              <label className={styles.rotulo} htmlFor="proteina-prato">
                Proteína
              </label>
              <select
                id="proteina-prato"
                className={styles.seletor}
                value={proteinaId}
                onChange={(e) => setProteinaId(e.target.value)}
              >
                <option value="">Escolha a proteína</option>
                {proteinasAtivas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome}
                  </option>
                ))}
              </select>
            </>
          )}
          <CampoFormulario
            rotulo="Gramas por porção"
            inputMode="numeric"
            value={gramas}
            onChange={(e) => setGramas(e.target.value)}
          />
          <p className={styles.nota}>A mesma gramagem vale para PF e marmita.</p>
          {desativadoRepetido && (
            <Aviso variante="aviso">
              <span>Já existe um prato desativado com esse nome. </span>
              <button type="button" onClick={() => reativarRepetido(desativadoRepetido)}>
                Reativar
              </button>
            </Aviso>
          )}
          {editando && (
            <Aviso variante="informacao">As vendas anteriores não mudam.</Aviso>
          )}
          {erro && <Aviso variante="falha">{erro}</Aviso>}
          <button className={styles.novo} type="submit" disabled={processando}>
            Salvar
          </button>
        </form>
      </PainelInferior>

      <DialogoConfirmacao
        aberto={paraDesativar !== null}
        titulo="Desativar prato?"
        consequencia="Ele sai dos cardápios novos. As vendas anteriores não mudam."
        rotuloAcao="Desativar prato"
        processando={processando}
        erro={erro ?? undefined}
        aoConfirmar={confirmarDesativar}
        aoFechar={() => setParaDesativar(null)}
      />
    </section>
  );
}
