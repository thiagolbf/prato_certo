import { redirect } from "next/navigation";

// A raiz não tem tela própria: quem abre o app cai direto no registro de venda.
export default function Home() {
  redirect("/registrar");
}
