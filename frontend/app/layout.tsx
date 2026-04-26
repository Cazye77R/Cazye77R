import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster }        from "sonner";
import ThemeProvider      from "@/components/layout/ThemeProvider";
import TopHeader          from "@/components/layout/TopHeader";
import BottomNav          from "@/components/layout/BottomNav";
import PageTransition     from "@/components/layout/PageTransition";
import SearchModal        from "@/components/layout/SearchModal";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default:  "StockMind – AI-powered Stock Analytics",
    template: "%s · StockMind",
  },
  description: "Premium AI stock analysis and portfolio management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      suppressHydrationWarning
    >
      <body className="bg-background text-foreground">
        <ThemeProvider>
          {/* Global Cmd+K search modal */}
          <SearchModal />

          <TopHeader />

          {/* Page content with enter transition */}
          <PageTransition>
            {children}
          </PageTransition>

          <BottomNav />

          {/* Toast notifications – sits above BottomNav */}
          <Toaster
            position="bottom-center"
            offset={84}
            theme="dark"
            toastOptions={{
              style: {
                background: "#1A2233",
                border:     "1px solid #2A3344",
                color:      "#E5E7EB",
                fontFamily: "var(--font-geist-sans)",
              },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
