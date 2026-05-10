import type { ReactNode } from "react";
import { cn } from "../../shared/cn";

const tones = {
  stone: "border-stone-300 bg-stone-100 text-stone-700",
  cyan: "border-cyan-200 bg-cyan-50 text-cyan-800",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  rose: "border-rose-200 bg-rose-50 text-rose-700",
  emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
} as const;

export function Badge({
  children,
  tone = "stone",
  className,
}: {
  children: ReactNode;
  tone?: keyof typeof tones;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex min-w-0 items-center rounded border px-1.5 py-0.5 text-xs font-medium leading-4",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
