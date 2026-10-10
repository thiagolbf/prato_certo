"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { CampoFormulario } from "@/components/CampoFormulario/CampoFormulario";
import { DialogoConfirmacao } from "@/components/DialogoConfirmacao/DialogoConfirmacao";
import { EstadoVazio } from "@/components/EstadoVazio/EstadoVazio";
import { ErroCarregamento } from "@/components/ErroCarregamento/ErroCarregamento";
import { ListaCadastro, type ItemCadastro } from "@/components/ListaCadastro/ListaCadastro";
import { PainelInferior } from "@/components/PainelInferior/PainelInferior";
import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";
import { Skeleton } from "@/components/Skeleton/Skeleton";
import { api, ErroApi } from "@/lib/api";

import styles from "../catalogo/catalogo.module.css";

// Espelha `UsuarioListado` de GET /api/usuarios.
type Usuario = {
  id: number;
  nome: string;
  login: string;
  perfil: "ADMIN" | "OPERADOR";
  ativo: boolean;
  bloqueado_ate: string | null;
};

type Estado = { tipo: "carregando" } | { tipo: "erro" } | { tipo: "pronto"; usuarios: Usuario[] };

const MINIMO_SENHA = 8;
const hora = (instante: string) =>
  new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" }).format(
    new Date(instante),
  );

// UI-12. Operadores: cadastro sem campo de perfil (RN-34), bloqueio marcado, redefinição de senha
// sempre disponível, mesmo com a conta bloqueada (RN-37, CA-51).
export default function PaginaUsuarios() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <TelaUsuarios />
    </RotaRestrita>
  );
}

function TelaUsuarios() {
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });
  const [tentativa, setTentativa] = useState(0);
  const [mostrarDesativados, setMostrarDesativados] = useState(false);
  const [novoAberto, setNovoAberto] = useState(false);
  const [nome, setNome] = useState("");
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<{ nome?: string; login?: string; senha?: string }>({});
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);
  const [paraDesativar, setParaDesativar] = useState<Usuario | null>(null);
  const [paraRedefinir, setParaRedefinir] = useState<Usuario | null>(null);
  const [senhaNova, setSenhaNova] = useState("");

  useEffect(() => {
    let ativo = true;
    api
      .get<Usuario[]>("/usuarios")
      .then((usuarios) => {
        if (ativo) setEstado({ tipo: "pronto", usuarios });
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
    setNovoAberto(false);
    setNome("");
    setLogin("");
    setSenha("");
    setErros({});
    setErroEnvio(null);
  }

  function cadastrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const novos: typeof erros = {};
    if (!nome.trim()) novos.nome = "Informe o nome.";
    if (!login.trim() || /\s/.test(login) || login.length > 30) novos.login = "Use até 30 caracteres, sem espaços.";
    if (senha.length < MINIMO_SENHA) novos.senha = `A senha precisa ter pelo menos ${MINIMO_SENHA} caracteres.`;
    setErros(novos);
    if (Object.keys(novos).length > 0) return;

    setProcessando(true);
    api
      .post("/usuarios", { nome: nome.trim(), login: login.trim(), senha })
      .then(() => {
        fechar();
        recarregar();
      })
      .catch((e: unknown) => setErroEnvio(e instanceof ErroApi && e.mensagem ? e.mensagem : "Não foi possível cadastrar agora."))
      .finally(() => setProcessando(false));
  }

  function acao(caminho: string, aoSucesso: () => void) {
    setProcessando(true);
    api
      .post(caminho)
      .then(aoSucesso)
      .catch((e: unknown) => setErroEnvio(e instanceof ErroApi && e.mensagem ? e.mensagem : "Não foi possível concluir agora."))
      .finally(() => setProcessando(false));
  }

  function redefinir() {
    if (!paraRedefinir) return;
    if (senhaNova.length < MINIMO_SENHA) {
      setErroEnvio(`A senha precisa ter pelo menos ${MINIMO_SENHA} caracteres.`);
      return;
    }
    setProcessando(true);
    api
      .post(`/usuarios/${paraRedefinir.id}/redefinir-senha`, { senha: senhaNova })
      .then(() => {
        setParaRedefinir(null);
        setSenhaNova("");
        setErroEnvio(null);
        recarregar();
      })
      .catch((e: unknown) => setErroEnvio(e instanceof ErroApi && e.mensagem ? e.mensagem : "Não foi possível redefinir agora."))
      .finally(() => setProcessando(false));
  }

  if (estado.tipo === "carregando") return <Skeleton linhas={4} />;
  if (estado.tipo === "erro") return <ErroCarregamento onTentarDeNovo={recarregar} />;

  const operadores = estado.usuarios.filter((u) => u.perfil === "OPERADOR");
  const itens: ItemCadastro[] = operadores.map((u) => ({
    id: u.id,
    nome: u.nome,
    ativo: u.ativo,
    detalhe: u.bloqueado_ate ? `Bloqueado até ${hora(u.bloqueado_ate)} · ${u.login}` : u.login,
  }));
  const porId = (id: number) => operadores.find((u) => u.id === id) ?? null;

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Usuários</h1>
      <button className={styles.novo} type="button" onClick={() => setNovoAberto(true)}>
        Novo operador
      </button>

      {operadores.length === 0 && <EstadoVazio titulo="Nenhum operador cadastrado." />}
      <ListaCadastro
        itens={itens}
        mostrarDesativados={mostrarDesativados}
        aoMudarFiltro={setMostrarDesativados}
        aoEditar={(item) => {
          setErroEnvio(null);
          setParaRedefinir(porId(item.id));
        }}
        aoDesativar={(item) => setParaDesativar(porId(item.id))}
        aoReativar={(item) => acao(`/usuarios/${item.id}/reativar`, recarregar)}
      />

      <PainelInferior aberto={novoAberto} titulo="Novo operador" aoFechar={fechar}>
        <form className={styles.formulario} onSubmit={cadastrar} noValidate>
          <CampoFormulario rotulo="Nome" value={nome} erro={erros.nome} onChange={(e) => setNome(e.target.value)} />
          <CampoFormulario
            rotulo="Usuário (até 30, sem espaços)"
            value={login}
            maxLength={30}
            autoCapitalize="none"
            erro={erros.login}
            onChange={(e) => setLogin(e.target.value)}
          />
          <CampoFormulario
            rotulo={`Senha inicial (mínimo de ${MINIMO_SENHA})`}
            type="password"
            autoComplete="new-password"
            value={senha}
            erro={erros.senha}
            onChange={(e) => setSenha(e.target.value)}
          />
          <p className={styles.nota}>Entregue a senha ao operador pessoalmente.</p>
          {erroEnvio && <Aviso variante="falha">{erroEnvio}</Aviso>}
          <button className={styles.novo} type="submit" disabled={processando}>
            Cadastrar operador
          </button>
        </form>
      </PainelInferior>

      <PainelInferior
        aberto={paraRedefinir !== null}
        titulo={paraRedefinir ? `Redefinir senha de ${paraRedefinir.nome}` : "Redefinir senha"}
        aoFechar={() => {
          setParaRedefinir(null);
          setSenhaNova("");
          setErroEnvio(null);
        }}
      >
        <CampoFormulario
          rotulo={`Nova senha (mínimo de ${MINIMO_SENHA})`}
          type="password"
          autoComplete="new-password"
          value={senhaNova}
          onChange={(e) => setSenhaNova(e.target.value)}
        />
        {erroEnvio && <Aviso variante="falha">{erroEnvio}</Aviso>}
        <button className={styles.novo} type="button" disabled={processando} onClick={redefinir}>
          Redefinir senha
        </button>
      </PainelInferior>

      <DialogoConfirmacao
        aberto={paraDesativar !== null}
        titulo={`Desativar ${paraDesativar?.nome ?? "operador"}?`}
        consequencia="Esse operador deixa de entrar. O histórico de vendas dele não muda."
        rotuloAcao="Desativar operador"
        processando={processando}
        erro={erroEnvio ?? undefined}
        aoConfirmar={() => {
          if (paraDesativar) acao(`/usuarios/${paraDesativar.id}/desativar`, () => {
            setParaDesativar(null);
            recarregar();
          });
        }}
        aoFechar={() => setParaDesativar(null)}
      />
    </section>
  );
}
