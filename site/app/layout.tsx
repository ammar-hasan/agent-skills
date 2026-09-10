import type { Metadata } from "next";
import "./globals.css";

const siteUrl = "https://ammar-hasan.github.io/agent-skills/";
const title = "Agent Skills — Good workflows. Shared as skills.";
const description =
  "A curated collection of practical skills for AI agents by Ammar Hasan. Explore the catalog, understand each workflow, and install what fits your work.";
const image = `${siteUrl}og.png`;

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title,
  description,
  alternates: { canonical: siteUrl },
  openGraph: {
    title,
    description,
    type: "website",
    url: siteUrl,
    siteName: "Agent Skills",
    images: [
      { url: image, alt: "Agent Skills: Good workflows. Shared as skills." },
    ],
  },
  twitter: { card: "summary_large_image", title, description, images: [image] },
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
