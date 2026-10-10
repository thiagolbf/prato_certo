import { api } from "@/lib/api";
import type { Formato } from "@/lib/cardapio";

// Espelha `FechamentoDiaListado` de GET /api/fechamento/dia. Valores monetários e datas chegam como texto.
export type UnidadesPorItem = { item_id: number; prato_nome: string; formato: Formato; unidades: number };
export type UnidadesPorPrato = { prato_nome: string; unidades: number };
export type ProteinaConsumida = { proteina_nome: string; gramas: number };
export type FaturamentoPorFormato = { formato: Formato; valor: string };
export type CancelamentoPosterior = {
  venda_id: number;
  prato_nome: string;
  quantidade: number;
  valor_total: string;
  cancelada_em: string;
  cancelada_por: string;
  motivo_cancelamento: string;
};

export type FechamentoDia = {
  data: string;
  parcial: boolean;
  total_unidades: number;
  unidades_por_item: UnidadesPorItem[];
  unidades_por_prato: UnidadesPorPrato[];
  proteina_por_tipo: ProteinaConsumida[];
  faturamento_por_formato: FaturamentoPorFormato[];
  faturamento_total: string;
  cancelamentos_posteriores: CancelamentoPosterior[];
};

export function buscarFechamentoDia(data: string): Promise<FechamentoDia> {
  return api.get<FechamentoDia>(`/fechamento/dia?data=${data}`);
}
