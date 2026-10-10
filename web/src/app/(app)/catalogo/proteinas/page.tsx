"use client";

import Link from "next/link";
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
  cadastrarProteina,
  desativarProteina,
  listarProteinas,
  reativarProteina,
  type Proteina,
} from "@/lib/proteinas";

import styles from "../catalogo.module.css";

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "pronto"; proteinas: Proteina[] };

const normalizar = (texto: string) => texto.trim().toLocaleLowerCase("pt-BR");

// UI-09. Lista de proteínas com contagem de pratos ativos; nome repetido, desativação bloqueada e
// reativação tratados aqui (RN-49, RN-58, CA-62).
export default function PaginaProteinas() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [mostrarDesativados, setMostrarDesativados] = useState(false);
  const [formularioAberto, setFormularioAberto] = useState(false);
  const [nomeNovo, setNomeNovo] = useState("");
  const [erroFormulario, setErroFormulario] = useState<string | null>(null);
  const [desativadaComMesmoNome, setDesativadaComMesmoNome] = useState<Proteina | null>(null);
  const [paraDesativar, setParaDesativar] = useState<Proteina | null>(null);
  const [processando, setProcessando] = useState(false);
  const [erroDesativar, setErroDesativar] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    listarProteinas()
      .then((proteinas) => {
        if (ativo) setEstado({ tipo: "pronto", proteinas });
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

  function fecharFormulario() {
    setFormularioAberto(false);
    setNomeNovo("");
    setErroFormulario(null);
    setDesativadaComMesmoNome(null);
  }

  function salvarNova(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (estado.tipo !== "pronto") return;
    const nome = nomeNovo.trim();
    if (!nome) {
      setErroFormulario("Informe o nome da proteína.");
      return;
    }
    const mesmoNome = estado.proteinas.find((p) => normalizar(p.nome) === normalizar(nome));
    if (mesmoNome?.ativo) {
      setErroFormulario("Já existe uma proteína com esse nome.");
      return;
    }
    if (mesmoNome && !mesmoNome.ativo) {
      setDesativadaComMesmoNome(mesmoNome);
      setErroFormulario(null);
      return;
    }
    setProcessando(true);
    cadastrarProteina(nome)
      .then(() => {
        fecharFormulario();
        recarregar();
      })
      .catch((erro: unknown) => {
        setErroFormulario(erro instanceof ErroApi && erro.mensagem ? erro.mensagem : "Não foi possível salvar agora.");
      })
      .finally(() => setProcessando(false));
  }

  function reativarRepetida(proteina: Proteina) {
    setProcessando(true);
    reativarProteina(proteina.id)
      .then(() => {
        fecharFormulario();
        recarregar();
      })
      .catch(() => setErroFormulario("Não foi possível reativar agora."))
      .finally(() => setProcessando(false));
  }

  function confirmarDesativar() {
    if (!paraDesativar) return;
    setProcessando(true);
    setErroDesativar(null);
    desativarProteina(paraDesativar.id)
      .then(() => {
        setParaDesativar(null);
        recarregar();
      })
      .catch((erro: unknown) => {
        // Desativação bloqueada: a API diz quais pratos ativos usam a proteína (RN-49).
        setErroDesativar(
          erro instanceof ErroApi && erro.mensagem ? erro.mensagem : "Não foi possível desativar agora.",
        );
      })
      .finally(() => setProcessando(false));
  }

  if (estado.tipo === "carregando") return <Skeleton linhas={4} />;
  if (estado.tipo === "erro") return <ErroCarregamento onTentarDeNovo={recarregar} />;

  const itens: ItemCadastro[] = estado.proteinas.map((p) => ({
    id: p.id,
    nome: p.nome,
    ativo: p.ativo,
    detalhe: `${p.pratos_ativos} ${p.pratos_ativos === 1 ? "prato ativo" : "pratos ativos"}`,
  }));

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Proteínas</h1>
      <button className={styles.novo} type="button" onClick={() => setFormularioAberto(true)}>
        Nova proteína
      </button>

      <ListaCadastro
        itens={itens}
        mostrarDesativados={mostrarDesativados}
        aoMudarFiltro={setMostrarDesativados}
        aoDesativar={(item) => {
          setErroDesativar(null);
          setParaDesativar(estado.proteinas.find((p) => p.id === item.id) ?? null);
        }}
        aoReativar={(item) => {
          setProcessando(true);
          reativarProteina(item.id)
            .then(recarregar)
            .finally(() => setProcessando(false));
        }}
      />

      <PainelInferior aberto={formularioAberto} titulo="Nova proteína" aoFechar={fecharFormulario}>
        <form className={styles.formulario} onSubmit={salvarNova} noValidate>
          <CampoFormulario
            rotulo="Nome"
            value={nomeNovo}
            disabled={processando}
            erro={erroFormulario ?? undefined}
            onChange={(evento) => {
              setNomeNovo(evento.target.value);
              setDesativadaComMesmoNome(null);
            }}
          />
          {desativadaComMesmoNome && (
            <Aviso variante="aviso">
              <span>Já existe uma proteína desativada com esse nome. </span>
              <button type="button" onClick={() => reativarRepetida(desativadaComMesmoNome)}>
                Reativar
              </button>
            </Aviso>
          )}
          <button className={styles.novo} type="submit" disabled={processando}>
            Salvar
          </button>
        </form>
      </PainelInferior>

      <DialogoConfirmacao
        aberto={paraDesativar !== null}
        titulo="Desativar proteína?"
        consequencia="Ela deixa de aparecer nos pratos novos. O histórico de vendas não muda."
        rotuloAcao="Desativar proteína"
        processando={processando}
        erro={
          erroDesativar ? (
            <>
              <p>{erroDesativar}</p>
              <Link className={styles.atalho} href="/catalogo/pratos">
                Ver os pratos
              </Link>
            </>
          ) : undefined
        }
        aoConfirmar={confirmarDesativar}
        aoFechar={() => setParaDesativar(null)}
      />
    </section>
  );
}
