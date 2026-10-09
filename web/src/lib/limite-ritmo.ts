// Limite de ritmo por origem, em janela deslizante (RN-37, camada 2; CA-34).
// Vive na borda, na memória da instância: nunca no processo da API (ADR-006). Em
// produção cada instância conta em separado, e o limite fica mais frouxo (plano, T-37).

export const LIMITE_POR_MINUTO = 10;
const JANELA_MS = 60_000;

export class LimiteDeRitmo {
  private readonly disparos = new Map<string, number[]>();

  constructor(
    private readonly limite: number = LIMITE_POR_MINUTO,
    private readonly janelaMs: number = JANELA_MS,
  ) {}

  // Devolve `true` se a tentativa cabe no limite, e a registra. Recusa sem registrar.
  permitir(origem: string, agora: number): boolean {
    const recentes = (this.disparos.get(origem) ?? []).filter(
      (instante) => agora - instante < this.janelaMs,
    );
    if (recentes.length >= this.limite) {
      this.disparos.set(origem, recentes);
      return false;
    }
    recentes.push(agora);
    this.disparos.set(origem, recentes);
    return true;
  }
}
