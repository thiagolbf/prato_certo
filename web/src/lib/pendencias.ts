import type { Formato } from "@/lib/cardapio";

// Venda que falhou por rede e ainda não foi registrada (RN-56). Fica no `sessionStorage` da aba:
// sobrevive a recarregar a página e some ao fechar a aba.
export type Pendencia = {
  chave: string;
  itemId: number;
  nomePrato: string;
  formato: Formato;
  quantidade: number;
  usuario: string;
  diaOperacional: string;
};

const CHAVE_ARMAZENAMENTO = "controle-pendencias-venda";

type Armazenamento = Pick<Storage, "getItem" | "setItem">;

// Armazenamento bloqueado (aba anônima, sem permissão) não pode derrubar a tela: a falha continua
// sinalizada na tela, só não persiste.
function armazenamentoPadrao(): Armazenamento | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function lerPendencias(armazenamento = armazenamentoPadrao()): Pendencia[] {
  try {
    const bruto = armazenamento?.getItem(CHAVE_ARMAZENAMENTO);
    return bruto ? (JSON.parse(bruto) as Pendencia[]) : [];
  } catch {
    return [];
  }
}

export function salvarPendencias(
  pendencias: Pendencia[],
  armazenamento = armazenamentoPadrao(),
): void {
  try {
    armazenamento?.setItem(CHAVE_ARMAZENAMENTO, JSON.stringify(pendencias));
  } catch {
    // Sem persistência: a pendência continua na memória da tela.
  }
}
