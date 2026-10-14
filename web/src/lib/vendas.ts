import { api } from "@/lib/api";
import type { Formato } from "@/lib/cardapio";

// Espelha `VendaDoDia` de GET /api/vendas/minhas. Sem preço nem valor (RN-40).
export type VendaDoDia = {
  id: number;
  horario: string;
  prato_nome: string;
  proteina_nome: string;
  formato: Formato;
  quantidade: number;
  cancelada: boolean;
};

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

export function listarMinhasVendas(): Promise<VendaDoDia[]> {
  return api.get<VendaDoDia[]>("/vendas/minhas");
}

// Espelha `VendaDaDataListada` de GET /api/vendas?data= (variante do ADMIN, com preço, valor e autor).
export type VendaDaData = VendaDoDia & {
  preco_unitario: string;
  valor_total: string;
  autor: string;
  cancelada_por: string | null;
  cancelada_em: string | null;
  motivo_cancelamento: string | null;
};

export type VendasDaData = {
  data: string;
  vendas: VendaDaData[];
  total_unidades: number;
  total_valor: string;
};

export function listarVendasDaData(data: string): Promise<VendasDaData> {
  return api.get<VendasDaData>(`/vendas?data=${data}`);
}

export function cancelarVenda(id: number, motivo: string): Promise<unknown> {
  return api.post(`/vendas/${id}/cancelar`, { motivo });
}
