"use client";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "sale" | "new" | "bestseller" | "outOfStock";
  className?: string;
}

const variantStyles = {
  default: "bg-warm-beige/50 text-charcoal",
  sale: "bg-rust text-cream",
  new: "bg-sage text-charcoal",
  bestseller: "bg-[#866a58] text-cream",
  outOfStock: "bg-espresso/10 text-espresso/60",
};

export function Badge({ children, variant = "default", className = "" }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center px-2.5 py-0.5 rounded-full
        text-xs font-medium tracking-wide
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {children}
    </span>
  );
}
