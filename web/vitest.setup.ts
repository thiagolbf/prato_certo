import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// Suíte paralela pode deixar as consultas assíncronas lentas: o padrão de 1 s causa falsos negativos.
configure({ asyncUtilTimeout: 4000 });

// Sem globals do Vitest, a Testing Library não desmonta sozinha entre os testes.
afterEach(() => {
  cleanup();
});
