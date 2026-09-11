import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "AutoAgent — Workspace",
  description:
    "Turn a goal into observable work, traceable evidence, and useful artifacts.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
