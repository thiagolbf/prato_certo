"use client";

import { RotaRestrita } from "@/components/AcessoNegado/AcessoNegado";

// Placeholder da rota de ADMIN: a guarda por perfil já está no lugar; a tela entra na T-47.
export default function VendasDaData() {
  return (
    <RotaRestrita perfis={["ADMIN"]}>
      <h1>Vendas da data</h1>
    </RotaRestrita>
  );
}
