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

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${urlDaApi()}/api/:path*` }];
  },
};

export default nextConfig;
