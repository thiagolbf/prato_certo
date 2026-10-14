"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Aviso } from "@/components/Aviso/Aviso";
import { CampoFormulario } from "@/components/CampoFormulario/CampoFormulario";
import { criarClienteApi, ErroApi, SessaoExpirada } from "@/lib/api";

import styles from "./login.module.css";

// Login não passa pelo redirecionamento de sessão expirada: um 401 aqui é credencial inválida.
const apiLogin = criarClienteApi(() => undefined);

const MENSAGEM_CREDENCIAL = "Usuário ou senha inválidos. Se o problema continuar, fale com o responsável.";
const MENSAGEM_LIMITE = "Muitas tentativas em pouco tempo. Aguarde alguns segundos e tente de novo.";
const MENSAGEM_ERRO = "Não foi possível entrar agora. Tente de novo.";

type Estado = "padrao" | "enviando" | "credencialInvalida" | "limiteRitmo" | "erro";

export function FormularioEntrar({ motivo }: { motivo?: string }) {
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<{ login?: string; senha?: string }>({});
  const [estado, setEstado] = useState<Estado>("padrao");

  async function entrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const novosErros: { login?: string; senha?: string } = {};
    if (!login.trim()) novosErros.login = "Informe o usuário.";
    if (!senha) novosErros.senha = "Informe a senha.";
    setErros(novosErros);
    if (Object.keys(novosErros).length > 0) return;

    setEstado("enviando");
    try {
      await apiLogin.post("/auth/login", { login: login.trim(), senha });
      router.replace("/registrar");
    } catch (erro) {
      if (erro instanceof SessaoExpirada) setEstado("credencialInvalida");
      else if (erro instanceof ErroApi && erro.status === 429) setEstado("limiteRitmo");
      else setEstado("erro");
    }
  }

  const enviando = estado === "enviando";

  return (
    <section className={styles.bloco}>
      <h1 className={styles.titulo}>Entrar</h1>

      {motivo === "sessao-expirada" && estado === "padrao" && (
        <Aviso variante="informacao">Sua sessão expirou. Entre de novo.</Aviso>
      )}
      {motivo === "saiu" && estado === "padrao" && <Aviso variante="informacao">Você saiu.</Aviso>}
      {estado === "credencialInvalida" && <Aviso variante="falha">{MENSAGEM_CREDENCIAL}</Aviso>}
      {estado === "limiteRitmo" && <Aviso variante="aviso">{MENSAGEM_LIMITE}</Aviso>}
      {estado === "erro" && <Aviso variante="falha">{MENSAGEM_ERRO}</Aviso>}

      <form className={styles.formulario} onSubmit={entrar} noValidate>
        <CampoFormulario
          rotulo="Usuário"
          name="login"
          autoComplete="username"
          autoCapitalize="none"
          maxLength={60}
          value={login}
          disabled={enviando}
          erro={erros.login}
          onChange={(evento) => setLogin(evento.target.value)}
        />
        <CampoFormulario
          rotulo="Senha"
          name="senha"
          type="password"
          autoComplete="current-password"
          value={senha}
          disabled={enviando}
          erro={erros.senha}
          onChange={(evento) => setSenha(evento.target.value)}
        />
        <button className={styles.entrar} type="submit" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        {enviando && (
          <p className={styles.aguarde}>
            A primeira conexão do dia pode levar alguns segundos.
          </p>
        )}
      </form>
    </section>
  );
}
