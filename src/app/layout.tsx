import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Modest Chic by Hira & Muqadas — Hijabs & Modest Fashion",
  description:
    "Discover Modest Chic hijabs and accessories in a collection of fabrics and shades.",
  keywords: [
    "hijab",
    "hijabs pakistan",
    "modest fashion",
    "chiffon hijab",
    "modal hijab",
    "jersey hijab",
    "premium hijabs",
    "pakistan hijab store",
    "modest chic",
  ],
  openGraph: {
    title: "Modest Chic by Hira & Muqadas — Hijabs & Modest Fashion",
    description:
      "Discover premium hijabs crafted for the modern woman. Elegance in every drape.",
    type: "website",
    locale: "en_PK",
  },
  icons: {
    icon: [
      { url: "/favicon.png?v=5", type: "image/png", sizes: "64x64" },
      { url: "/favicon.ico?v=5", type: "image/x-icon", sizes: "32x32" },
    ],
    apple: [{ url: "/apple-touch-icon.png?v=5", sizes: "180x180" }],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${inter.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-cream text-charcoal">
        {children}
      </body>
    </html>
  );
}
