import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const DESCRIPTION =
  "Doppelganger runs your Qualtrics survey through AI respondents in minutes, so you can catch problems and gauge your effect before you pay for human participants.";

export const metadata: Metadata = {
  metadataBase: new URL("https://doppelgangerlabs.com"),
  title: {
    default: "Doppelganger — Pretest your survey with AI respondents",
    template: "%s — Doppelganger",
  },
  description: DESCRIPTION,
  applicationName: "Doppelganger",
  keywords: [
    "survey pretesting",
    "AI survey respondents",
    "synthetic respondents",
    "silicon sampling",
    "pilot study",
    "Qualtrics survey",
    "behavioral research",
    "consumer research",
    "manipulation check",
    "statistical power",
    "MTurk",
    "Prolific",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "https://doppelgangerlabs.com",
    siteName: "Doppelganger",
    title: "Pretest your survey with AI respondents before you pay",
    description: DESCRIPTION,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Pretest your survey with AI respondents before you pay",
    description: DESCRIPTION,
  },
};

// Organization + product structured data so search engines (and AI answer engines)
// understand what we are. Emitted as an @graph so the Organization is a single shared
// entity that the product, website, and every article/blog page can reference by @id.
const SITE = "https://doppelgangerlabs.com";
const ORG_ID = `${SITE}/#organization`;

const JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": ORG_ID,
      name: "Doppelganger Labs",
      url: SITE,
      logo: {
        "@type": "ImageObject",
        url: `${SITE}/logo.svg`,
        width: 512,
        height: 512,
      },
      description: DESCRIPTION,
      email: "hello@doppelgangerlabs.com",
      // Add public profiles here (X, LinkedIn, GitHub) to strengthen the knowledge
      // entity Google/AI engines build for the brand, e.g.:
      // sameAs: ["https://x.com/...", "https://www.linkedin.com/company/..."],
    },
    {
      "@type": "WebSite",
      "@id": `${SITE}/#website`,
      url: SITE,
      name: "Doppelganger",
      description: DESCRIPTION,
      publisher: { "@id": ORG_ID },
    },
    {
      "@type": "SoftwareApplication",
      name: "Doppelganger",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      url: SITE,
      description: DESCRIPTION,
      publisher: { "@id": ORG_ID },
      offers: {
        "@type": "Offer",
        price: "7.99",
        priceCurrency: "USD",
      },
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
        />
        {children}
      </body>
    </html>
  );
}
