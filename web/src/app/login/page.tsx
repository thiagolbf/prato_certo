import { FormularioEntrar } from "./FormularioEntrar";

// UI-01. O motivo vem da URL (`sessao-expirada` ou `saiu`), gravado pelo cliente da API e pelo AppShell.
export default async function PaginaEntrar({
  searchParams,
}: {
  searchParams: Promise<{ motivo?: string | string[] }>;
}) {
  const { motivo } = await searchParams;
  return (
    <main>
      <FormularioEntrar motivo={typeof motivo === "string" ? motivo : undefined} />
    </main>
  );
}
