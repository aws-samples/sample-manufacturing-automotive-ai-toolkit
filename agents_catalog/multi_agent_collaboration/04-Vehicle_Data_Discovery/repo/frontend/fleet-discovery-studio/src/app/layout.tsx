import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth/AuthProvider";

// Apple-like Sans Serif
const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

// Engineering Monospace
const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: "Autonomous Fleet Discovery Platform",
  description: "Engineering Laboratory for HIL Scenario Discovery and Cost-Optimized Training Data Curation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="antialiased bg-[var(--soft-grey)]">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
