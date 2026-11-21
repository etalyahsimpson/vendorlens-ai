export default function Footer() {
  return (
    <footer className="mt-auto border-t border-navy-100 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 py-4 text-xs text-navy-500 sm:flex-row sm:px-6">
        <p>
          VendorLens AI · Independent Engineering Portfolio Project · © 2026 Etalyah
          Simpson · All rights reserved.
        </p>
        <a
          href="https://etalyahsimpson.github.io/"
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-navy-700 underline-offset-2 hover:text-brand-teal hover:underline"
        >
          Official Portfolio ↗
        </a>
      </div>
    </footer>
  );
}
