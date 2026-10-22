export function Logo({ className = "size-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="mp-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="oklch(0.66 0.17 245)" />
          <stop offset="100%" stopColor="oklch(0.5 0.21 268)" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#mp-logo)" />
      {/* Pendrive estilizado */}
      <rect x="22" y="10" width="20" height="13" rx="2.5" fill="white" opacity="0.55" />
      <rect x="27" y="14" width="3" height="4" rx="0.8" fill="url(#mp-logo)" />
      <rect x="34" y="14" width="3" height="4" rx="0.8" fill="url(#mp-logo)" />
      <rect x="16" y="21" width="32" height="34" rx="7" fill="white" />
      {/* Marca de "pronto" */}
      <path d="M24.5 38.5 L30 44 L40.5 32.5" fill="none" stroke="url(#mp-logo)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
