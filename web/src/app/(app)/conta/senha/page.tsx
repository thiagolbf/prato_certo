"use client";

import { useState, type FormEvent } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { CampoFormulario } from "@/components/CampoFormulario/CampoFormulario";
import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";
import { api, ErroApi } from "@/lib/api";

import styles from "./senha.module.css";

const MINIMO = 8;

// UI-13. Trocar a própria senha: só o ADMIN chega aqui (o Operador não troca a senha, RN-52).
export default function PaginaTrocarSenha() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <TelaTrocarSenha />
    </RotaRestrita>
  );
}

function TelaTrocarSenha() {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repeticao, setRepeticao] = useState("");
  const [erros, setErros] = useState<{ atual?: string; nova?: string; repeticao?: string }>({});
  const [enviando, setEnviando] = useState(false);
  const [sucesso, setSucesso] = useState(false);
  const [falha, setFalha] = useState<string | null>(null);

  function validar(): boolean {
    const novosErros: typeof erros = {};
    if (!atual) novosErros.atual = "Informe a senha atual.";
    if (nova.length < MINIMO) novosErros.nova = `A nova senha precisa ter pelo menos ${MINIMO} caracteres.`;
    if (repeticao !== nova) novosErros.repeticao = "As senhas não conferem.";
    setErros(novosErros);
    return Object.keys(novosErros).length === 0;
  }

  function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setSucesso(false);
    setFalha(null);
    if (!validar()) return;

    setEnviando(true);
    api
      .post("/conta/senha", { senha_atual: atual, senha_nova: nova })
      .then(() => {
        setSucesso(true);
        setAtual("");
        setNova("");
        setRepeticao("");
      })
      .catch((erro: unknown) => {
        if (erro instanceof ErroApi && erro.status === 422) {
          // Senha atual incorreta ou conta bloqueada: a API não distingue, e a tela também não.
          setErros({ atual: erro.mensagem ?? "Senha atual incorreta." });
        } else {
          setFalha("Não foi possível alterar a senha agora. Tente de novo.");
        }
      })
      .finally(() => setEnviando(false));
  }

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Trocar minha senha</h1>
      {sucesso && <Aviso variante="sucesso">Senha alterada.</Aviso>}
      {falha && <Aviso variante="falha">{falha}</Aviso>}

      <form className={styles.formulario} onSubmit={salvar} noValidate>
        <CampoFormulario
          rotulo="Senha atual"
          type="password"
          autoComplete="current-password"
          value={atual}
          disabled={enviando}
          erro={erros.atual}
          onChange={(e) => setAtual(e.target.value)}
        />
        <CampoFormulario
          rotulo="Nova senha"
          type="password"
          autoComplete="new-password"
          value={nova}
          disabled={enviando}
          erro={erros.nova}
          onChange={(e) => setNova(e.target.value)}
        />
        <CampoFormulario
          rotulo="Repita a nova senha"
          type="password"
          autoComplete="new-password"
          value={repeticao}
          disabled={enviando}
          erro={erros.repeticao}
          onChange={(e) => setRepeticao(e.target.value)}
        />
        <button className={styles.salvar} type="submit" disabled={enviando}>
          {enviando ? "Salvando…" : "Salvar nova senha"}
        </button>
      </form>
    </section>
  );
}
