"use client";

import Link from "next/link";

import { Aviso } from "@/components/Aviso/Aviso";
import { formatarDataCurta } from "@/lib/formato";

// Aviso para o ADMIN quando o cardápio de hoje é herdado de um dia anterior (RN-09).
export function AvisoCardapioHerdado({ dataOrigem }: { dataOrigem: string }) {
  return (
    <Aviso variante="aviso">
      <span>Cardápio de hoje herdado de {formatarDataCurta(dataOrigem)}. </span>
      <Link href="/cardapio">Revisar cardápio</Link>
    </Aviso>
  );
}
