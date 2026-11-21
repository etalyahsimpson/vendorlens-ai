/** Brand mark: a lens over connected supplier records. */
export default function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="VendorLens AI logo"
      className="shrink-0"
    >
      <rect x="4" y="4" width="56" height="56" rx="14" fill="#10233C" />
      <circle cx="28" cy="28" r="13" fill="none" stroke="#2DD4BF" strokeWidth="4.5" />
      <line x1="38" y1="38" x2="49" y2="49" stroke="#2DD4BF" strokeWidth="5.5" strokeLinecap="round" />
      <circle cx="24" cy="30" r="2.6" fill="#F59E0B" />
      <circle cx="32" cy="24" r="2.6" fill="#2DD4BF" />
      <circle cx="33" cy="32" r="2.6" fill="#F8FAFC" />
    </svg>
  );
}
