// Cliente HTTP da Web (ADR-006): caminhos relativos `/api/…`, same-origin, com o cookie de sessão
// que o navegador já carrega. Não guarda token nem usa armazenamento do navegador.

export class SessaoExpirada extends Error {
  constructor() {
    super("Sessão expirada");
    this.name = "SessaoExpirada";
  }
}

// `mensagem` é o texto de negócio que a API devolve em `detail` (por exemplo, dependentes de um
// cadastro). Não é detalhe técnico: erros sem texto de negócio ficam com `undefined`.
export class ErroApi extends Error {
  constructor(
    readonly status: number,
    readonly mensagem?: string,
  ) {
    super(`A API respondeu ${status}`);
    this.name = "ErroApi";
  }
}

type Metodo = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type Api = {
  get<T>(caminho: string): Promise<T>;
  post<T = void>(caminho: string, corpo?: unknown): Promise<T>;
};

// `aoSessaoExpirada` é chamado num 401 antes de a Promise rejeitar; na aplicação ele leva ao login.
// `fetchImpl` existe para teste: sem ele, usa o `fetch` global no momento da chamada.
export function criarClienteApi(
  aoSessaoExpirada: () => void,
  fetchImpl?: typeof fetch,
): Api {
  async function chamar<T>(metodo: Metodo, caminho: string, corpo?: unknown): Promise<T> {
    const cabecalhos: Record<string, string> = { Accept: "application/json" };
    if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";

    const resposta = await (fetchImpl ?? fetch)(`/api${caminho}`, {
      method: metodo,
      credentials: "same-origin",
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });

    if (resposta.status === 401) {
      aoSessaoExpirada();
      throw new SessaoExpirada();
    }
    if (!resposta.ok) {
      const corpoErro = (await resposta.json().catch(() => undefined)) as { detail?: unknown } | undefined;
      throw new ErroApi(resposta.status, typeof corpoErro?.detail === "string" ? corpoErro.detail : undefined);
    }
    if (resposta.status === 204) return undefined as T;
    return (await resposta.json()) as T;
  }

  return {
    get: (caminho) => chamar("GET", caminho),
    post: (caminho, corpo) => chamar("POST", caminho, corpo),
  };
}

// Na aplicação, sessão expirada leva ao login com o motivo na URL (UI-01.sessaoExpirada).
export const api = criarClienteApi(() => {
  window.location.replace("/login?motivo=sessao-expirada");
});
