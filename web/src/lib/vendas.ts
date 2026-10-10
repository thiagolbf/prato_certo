import { api } from "@/lib/api";

// Espelha `VendaRegistrada` de POST /api/vendas (201 criada, 200 quando a chave já existia).
export type VendaRegistrada = {
  id: number;
  item_id: number;
  quantidade: number;
};

export type NovaVenda = {
  itemId: number;
  quantidade: number;
  chave: string;
};

// A chave de idempotência nasce no toque em Confirmar (RN-18). Reenviar usa a mesma chave.
export function gerarChave(): string {
  return crypto.randomUUID();
}

export function registrarVenda(venda: NovaVenda): Promise<VendaRegistrada> {
  return api.post<VendaRegistrada>("/vendas", {
    item_id: venda.itemId,
    quantidade: venda.quantidade,
    chave_idempotencia: venda.chave,
  });
}
