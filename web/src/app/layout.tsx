import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Controle de PF e Marmitas",
  description: "Registro de PF e marmitas vendidos e fechamento do dia",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
