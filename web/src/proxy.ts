// Proxy da Web (Next 16 chama de `proxy`, antes `middleware`): aplica o limite de ritmo só em
// POST /api/auth/login (RN-37, camada 2; CA-34). Nenhuma outra rota passa pelo limite, e a
// conta nunca muda de estado por causa dele (a API não é consultada quando o limite recusa).
import { NextRequest, NextResponse } from "next/server";

import { LimiteDeRitmo } from "./lib/limite-ritmo";

const limiteDeLogin = new LimiteDeRitmo();

// Só a primeira parte de X-Forwarded-For, e só porque a plataforma o define (plano, T-37).
// Localmente o cabeçalho não existe e todas as requisições caem na mesma origem.
function origemDaRequisicao(request: NextRequest): string {
  const encaminhado = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return encaminhado || "local";
}

export function proxy(request: NextRequest) {
  const eLogin = request.method === "POST" && request.nextUrl.pathname === "/api/auth/login";
  if (!eLogin) {
    return NextResponse.next();
  }
  if (!limiteDeLogin.permitir(origemDaRequisicao(request), Date.now())) {
    return NextResponse.json(
      { detail: "Muitas tentativas de login. Aguarde um minuto." },
      { status: 429 },
    );
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/api/:path*",
};
