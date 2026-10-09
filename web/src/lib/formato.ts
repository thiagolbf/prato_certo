// Formatadores de PT-BR da SPEC-UI, seção 9. Recebem texto como a API devolve: valores
// monetários e datas chegam como string, e a conversão para número não passa por float.

const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

function separarMilhar(digitos: string): string {
  return digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

// `1234.5` ou `"1234.50"` -> `R$ 1.234,50`.
export function formatarMoeda(valor: string): string {
  const [inteiro, centavos = ""] = valor.split(".");
  const sinal = inteiro.startsWith("-") ? "-" : "";
  const digitos = inteiro.replace("-", "");
  return `R$ ${sinal}${separarMilhar(digitos)},${centavos.padEnd(2, "0")}`;
}

// `"2026-09-05"` -> `05/09`.
export function formatarDataCurta(data: string): string {
  const [, mes, dia] = data.split("-");
  return `${dia}/${mes}`;
}

// `"2026-09"` -> `setembro 2026`.
export function formatarMesPorExtenso(mes: string): string {
  const [ano, numero] = mes.split("-");
  return `${MESES[Number(numero) - 1]} ${ano}`;
}

// Gramas com separador de milhar; a partir de 1.000 g, o peso em kg aparece ao lado.
// `2100` -> `2.100 g (2,1 kg)`; `450` -> `450 g`.
export function formatarGramas(gramas: number): string {
  const texto = `${separarMilhar(String(gramas))} g`;
  if (gramas < 1000) {
    return texto;
  }
  const kg = (gramas / 1000).toFixed(1).replace(".", ",");
  return `${texto} (${kg} kg)`;
}
