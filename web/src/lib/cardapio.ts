// Espelha `CardapioListado` e `ItemVigenteListado` da API (GET /api/cardapio/vigente).
// Datas vêm como `AAAA-MM-DD` e preço como texto decimal, sem passar por float.
export type TipoCardapio = "PROPRIO" | "HERDADO" | "VAZIO";
export type Formato = "PF" | "MARMITA";

export type ItemCardapio = {
  item_id: number;
  nome_prato: string;
  nome_proteina: string;
  formato: Formato;
  gramas_por_porcao: number;
  preco: string;
};

export type CardapioVigente = {
  data: string;
  tipo: TipoCardapio;
  data_origem: string | null;
  itens: ItemCardapio[];
};
