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

// Espelha `CardapioDaDataListado` de GET /api/cardapio?data= (ADMIN). `passada` é true em data anterior a hoje.
export type CardapioDaData = CardapioVigente & { passada: boolean };

// Espelha `ItemListado` de GET /api/itens (catálogo do ADMIN).
export type ItemDoCatalogo = {
  id: number;
  prato_id: number;
  prato_nome: string;
  nome: string;
  formato: Formato;
  gramas_por_porcao: number;
  preco: string;
  ativo: boolean;
};
