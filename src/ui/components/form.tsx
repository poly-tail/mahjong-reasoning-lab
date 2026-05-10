import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";
import { cn } from "../../shared/cn";

export function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={cn("grid gap-1.5 text-sm text-stone-700", className)}>
      <span className="font-medium text-stone-800">{label}</span>
      {children}
      {hint ? <span className="text-xs text-stone-500">{hint}</span> : null}
    </label>
  );
}

export const Input = forwardRef<
  HTMLInputElement,
  ComponentPropsWithoutRef<"input">
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-8 rounded-md border border-stone-300 bg-white px-2 text-sm text-stone-900 outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  ComponentPropsWithoutRef<"textarea">
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-20 rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm text-stone-900 outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export const Select = forwardRef<
  HTMLSelectElement,
  ComponentPropsWithoutRef<"select">
>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "h-8 rounded-md border border-stone-300 bg-white px-2 text-sm text-stone-900 outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100",
      className,
    )}
    {...props}
  />
));
Select.displayName = "Select";
