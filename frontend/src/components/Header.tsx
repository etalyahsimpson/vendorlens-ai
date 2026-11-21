import Logo from "./Logo";
import type { ViewId } from "../App";

interface HeaderProps {
  active: ViewId;
  onNavigate: (view: ViewId) => void;
  apiDocsUrl: string;
}

const NAV: { id: ViewId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "review", label: "Review Matches" },
  { id: "model", label: "Model Performance" },
];

export default function Header({ active, onNavigate, apiDocsUrl }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-navy-100 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <button
          className="flex items-center gap-3 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal"
          onClick={() => onNavigate("overview")}
          aria-label="VendorLens AI home"
        >
          <Logo />
          <div className="text-left leading-tight">
            <div className="text-[15px] font-bold tracking-tight text-navy-900">
              VendorLens <span className="text-brand-teal">AI</span>
            </div>
            <div className="hidden text-[11px] font-medium text-navy-500 sm:block">
              Supplier Identity &amp; Duplicate Detection
            </div>
          </div>
        </button>

        <nav aria-label="Primary" className="flex items-center gap-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              aria-current={active === item.id ? "page" : undefined}
              className={`rounded-md px-3 py-2 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal ${
                active === item.id
                  ? "bg-navy-50 text-navy-900"
                  : "text-navy-500 hover:bg-navy-50 hover:text-navy-800"
              } ${item.id === "review" ? "hidden md:inline-block" : ""}`}
            >
              {item.label}
            </button>
          ))}
          <a
            href={apiDocsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 hidden rounded-md px-3 py-2 text-sm font-semibold text-navy-500 transition-colors hover:bg-navy-50 hover:text-navy-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal sm:inline-block"
          >
            API Docs ↗
          </a>
        </nav>
      </div>
    </header>
  );
}
