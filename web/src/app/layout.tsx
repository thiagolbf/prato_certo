import type { Metadata } from "next";
import { Nunito_Sans } from "next/font/google";
import "./globals.css";

// Nunito Sans hospedada pelo próprio Next, junto com a aplicação (SPEC-UI 2, ADR-008).
const nunitoSans = Nunito_Sans({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Controle de PF e Marmitas",
  description: "Registro de PF e marmitas vendidos e fechamento do dia",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={nunitoSans.className}>
      <body>{children}</body>
    </html>
  );
}
