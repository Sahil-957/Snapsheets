import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bulk OCR Extractor",
  description: "Upload structured screenshots, extract data, and export to Excel.",
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
