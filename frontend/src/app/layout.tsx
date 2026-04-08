import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Warehouse Simulator",
  description: "3D Warehouse Simulation for AI Agents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
