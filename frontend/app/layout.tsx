import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedRep AI",
  description: "Ask questions about approved product documents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
