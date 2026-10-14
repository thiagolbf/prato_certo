import { api } from "@/lib/api";

// Espelha `ProteinaListada` de GET /api/proteinas.
export type Proteina = {
  id: number;
  nome: string;
  ativo: boolean;
  pratos_ativos: number;
};

export function listarProteinas(): Promise<Proteina[]> {
  return api.get<Proteina[]>("/proteinas");
}

export function cadastrarProteina(nome: string): Promise<Proteina> {
  return api.post<Proteina>("/proteinas", { nome });
}

export function desativarProteina(id: number): Promise<Proteina> {
  return api.post<Proteina>(`/proteinas/${id}/desativar`);
}

export function reativarProteina(id: number): Promise<Proteina> {
  return api.post<Proteina>(`/proteinas/${id}/reativar`);
}
