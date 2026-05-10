import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../shared/cn";

const buttonVariants = cva(
  "inline-flex h-8 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        primary: "border-cyan-700 bg-cyan-700 text-white hover:bg-cyan-800",
        secondary:
          "border-stone-300 bg-white text-stone-800 hover:bg-stone-100",
        ghost:
          "border-transparent bg-transparent text-stone-700 hover:bg-stone-100",
        danger: "border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100",
      },
      size: {
        sm: "h-7 px-2 text-xs",
        md: "h-8 px-2.5 text-sm",
        icon: "h-8 w-8 px-0",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
);

export type ButtonProps = ComponentPropsWithoutRef<"button"> &
  VariantProps<typeof buttonVariants>;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);

Button.displayName = "Button";
