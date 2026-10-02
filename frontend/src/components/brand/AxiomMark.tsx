import { cn } from "@/lib/utils";

/** Minimal geometric Axiom mark — axis + open A. */
export function AxiomMark({
  className,
  size = 40,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-[13px]",
        "bg-[linear-gradient(145deg,#151821_0%,#22262f_55%,#1a3d38_100%)]",
        "shadow-soft ring-1 ring-white/10 transition duration-200 group-hover:scale-[1.03]",
        className
      )}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg
        viewBox="0 0 40 40"
        width={size * 0.62}
        height={size * 0.62}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Open A — two strokes */}
        <path
          d="M12 30 L20 10 L28 30"
          stroke="white"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Crossbar as soft accent */}
        <path
          d="M15.5 22.5 H24.5"
          stroke="#43C0A8"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        {/* Baseline node — tech detail */}
        <circle cx="20" cy="30" r="1.6" fill="#43C0A8" opacity="0.9" />
      </svg>
      {/* Soft top highlight */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-1/2 bg-gradient-to-b from-white/10 to-transparent" />
    </div>
  );
}
