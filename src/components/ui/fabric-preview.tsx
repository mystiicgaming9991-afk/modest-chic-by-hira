interface FabricPreviewProps {
  color: string;
  name: string;
  className?: string;
}

export function FabricPreview({ color, name, className = "" }: FabricPreviewProps) {
  return (
    <div className={`relative overflow-hidden bg-[#e8dcd4] ${className}`} role="img" aria-label={`${name} fabric colour preview`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_26%,#fff9_0%,transparent_67%)] opacity-70" />
      <div className="absolute inset-x-[10%] bottom-[5%] h-[12%] rounded-full bg-[#43342f]/20 blur-xl" />
      <svg viewBox="0 0 320 400" className="absolute inset-0 h-full w-full drop-shadow-[5px_12px_12px_rgba(50,34,31,0.24)]" aria-hidden="true">
        <defs>
          <linearGradient id={`fold-${name.replace(/\W/g, "")}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity=".38" />
            <stop offset="42%" stopColor={color} />
            <stop offset="100%" stopColor="#211816" stopOpacity=".4" />
          </linearGradient>
        </defs>
        <path d="M65 68 C101 32 217 29 256 69 C222 126 245 172 267 274 C280 333 241 365 179 378 C139 342 74 356 42 306 C22 271 45 203 66 157 C75 130 53 100 65 68Z" fill={color} />
        <path d="M65 68 C105 108 126 157 106 225 C89 288 118 331 179 378 C120 341 60 357 42 306 C23 255 47 201 66 157 C75 130 53 100 65 68Z" fill="#fff" opacity=".19" />
        <path d="M256 69 C220 113 199 155 214 213 C229 279 214 344 179 378 C246 363 281 330 267 274 C245 172 222 126 256 69Z" fill="#201514" opacity=".18" />
        <path d="M65 68 C101 32 217 29 256 69 C232 110 207 116 164 127 C121 112 91 107 65 68Z" fill={`url(#fold-${name.replace(/\W/g, "")})`} opacity=".72" />
        <path d="M65 68 C89 115 103 157 95 220 M256 69 C222 120 219 169 234 236" fill="none" stroke="#fff" strokeOpacity=".35" strokeWidth="2" />
      </svg>
      <span className="absolute bottom-3 right-3 hidden rounded-full bg-cream/90 px-2.5 py-1 text-[10px] font-medium tracking-wide text-charcoal shadow-sm sm:block">Colour preview</span>
    </div>
  );
}
