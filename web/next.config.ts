import type { NextConfig } from "next";

// O navegador só conversa com a Web: /api/* é reescrito para a API, que fica
// same-origin e dispensa CORS (ADR-006). A URL vem só do ambiente (ADR-008).
function urlDaApi(): string {
  const url = process.env.API_URL;
  if (!url) {
    throw new Error("Defina API_URL (veja web/.env.example).");
  }
  return url.replace(/\/+$/, "");
}

// CSP restritiva: só a própria origem, sem domínio externo (a fonte sai do next/font, servida
// localmente). `unsafe-eval` só entra em desenvolvimento, para o hot reload do Next.
export function cabecalhosDeSeguranca(emDesenvolvimento: boolean): { key: string; value: string }[] {
  const scriptSrc = emDesenvolvimento
    ? "'self' 'unsafe-inline' 'unsafe-eval'"
    : "'self' 'unsafe-inline'";
  const csp = [
    "default-src 'self'",
    `script-src ${scriptSrc}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
  return [
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Content-Security-Policy", value: csp },
  ];
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${urlDaApi()}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: cabecalhosDeSeguranca(process.env.NODE_ENV !== "production"),
      },
    ];
  },
};

export default nextConfig;
