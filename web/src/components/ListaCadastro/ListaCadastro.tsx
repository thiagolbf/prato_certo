"use client";

import { Etiqueta } from "@/components/Etiqueta/Etiqueta";

import styles from "./ListaCadastro.module.css";

export type ItemCadastro = {
  id: number;
  nome: string;
  ativo: boolean;
  detalhe?: string;
};

// Lista de cadastro comum às telas do catálogo (UI-09 a UI-12): ordem alfabética, filtro de
// desativados e ações por item. Desativar e reativar são decididos pela tela que usa a lista.
export function ListaCadastro({
  itens,
  mostrarDesativados,
  aoMudarFiltro,
  aoDesativar,
  aoReativar,
  aoEditar,
}: {
  itens: ItemCadastro[];
  mostrarDesativados: boolean;
  aoMudarFiltro: (mostrar: boolean) => void;
  aoDesativar: (item: ItemCadastro) => void;
  aoReativar: (item: ItemCadastro) => void;
  aoEditar?: (item: ItemCadastro) => void;
}) {
  const visiveis = itens
    .filter((item) => mostrarDesativados || item.ativo)
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));

  return (
    <div className={styles.bloco}>
      <label className={styles.filtro}>
        <input
          type="checkbox"
          checked={mostrarDesativados}
          onChange={(evento) => aoMudarFiltro(evento.target.checked)}
        />
        Mostrar desativados
      </label>
      <ul className={styles.lista}>
        {visiveis.map((item) => (
          <li className={styles.item} key={item.id}>
            <div className={styles.corpo}>
              <span className={styles.nome}>{item.nome}</span>
              {item.detalhe && <span className={styles.detalhe}>{item.detalhe}</span>}
            </div>
            <div className={styles.acoes}>
              {!item.ativo && <Etiqueta variante="desativado" />}
              {item.ativo && aoEditar && (
                <button className={styles.acao} type="button" onClick={() => aoEditar(item)}>
                  Editar
                </button>
              )}
              {item.ativo ? (
                <button className={styles.acao} type="button" onClick={() => aoDesativar(item)}>
                  Desativar
                </button>
              ) : (
                <button className={styles.acao} type="button" onClick={() => aoReativar(item)}>
                  Reativar
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
