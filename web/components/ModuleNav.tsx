"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const MODULES = [
  { href: "/", label: "Overview" },
  { href: "/reconciliation", label: "Reconciliation" },
  { href: "/reporting", label: "Reporting" },
  { href: "/data-quality", label: "Data Quality" },
  { href: "/documents", label: "Documents" },
  { href: "/ledger", label: "Ledger" },
];

export default function ModuleNav() {
  const path = usePathname();
  return (
    <nav className="modnav">
      {MODULES.map((m) => (
        <Link
          key={m.href}
          href={m.href}
          className={path === m.href ? "active" : ""}
        >
          {m.label}
        </Link>
      ))}
    </nav>
  );
}
