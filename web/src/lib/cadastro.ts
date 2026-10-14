import { api } from "@/lib/api";
import type { Formato } from "@/lib/cardapio";

// Espelha `PratoListado` de GET /api/pratos.
export type Prato = {
  id: number;
  nome: string;
  proteina_id: number;
  proteina_nome: string;
  gramas_por_porcao: number;
  ativo: boolean;
  itens_ativos: number;
};

// Espelha `ItemListado` de GET /api/itens.
export type ItemDeCardapio = {
  id: number;
  prato_id: number;
  prato_nome: string;
  nome: string;
  formato: Formato;
  gramas_por_porcao: number;
  preco: string;
  ativo: boolean;
};

export const listarPratos = () => api.get<Prato[]>("/pratos");
export const cadastrarPrato = (dados: { nome: string; proteina_id: number; gramas_por_porcao: number }) =>
  api.post<Prato>("/pratos", dados);
export const alterarGramagem = (id: number, gramas: number) =>
  api.post<Prato>(`/pratos/${id}/gramagem`, { gramas_por_porcao: gramas });
export const desativarPrato = (id: number) => api.post<Prato>(`/pratos/${id}/desativar`);
export const reativarPrato = (id: number) => api.post<Prato>(`/pratos/${id}/reativar`);

export const listarItens = () => api.get<ItemDeCardapio[]>("/itens");
export const cadastrarItem = (dados: { prato_id: number; formato: Formato; preco: string }) =>
  api.post<ItemDeCardapio>("/itens", dados);
export const alterarPreco = (id: number, preco: string) => api.post<ItemDeCardapio>(`/itens/${id}/preco`, { preco });
export const desativarItem = (id: number) => api.post<ItemDeCardapio>(`/itens/${id}/desativar`);
export const reativarItem = (id: number) => api.post<ItemDeCardapio>(`/itens/${id}/reativar`);
