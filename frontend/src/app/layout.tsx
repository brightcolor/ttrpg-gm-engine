import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TTRPG GM Engine",
  description: "Self-hostable AI gamemaster campaign engine"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}

