import type { Metadata } from "next";
import "./globals.css";
import MarketBar from "../components/MarketBar";
import ModuleNav from "../components/ModuleNav";

export const metadata: Metadata = {
  title: "Investment Operations Suite",
  description:
    "Live back-office platform — reconciliation, reporting, data quality, documents, ledger",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <MarketBar />
        <div className="shell">
          <ModuleNav />
          {children}
        </div>
      </body>
    </html>
  );
}
