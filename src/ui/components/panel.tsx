import type { ReactNode } from "react";
import { cn } from "../../shared/cn";

export function Panel({
  title,
  action,
  className,
  children,
}: {
  title?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn("rounded-lg border border-stone-200 bg-white", className)}
    >
      {title || action ? (
        <div className="flex h-10 items-center justify-between gap-2 border-b border-stone-200 px-3">
          {title ? (
            <h2 className="truncate text-sm font-semibold text-stone-900">
              {title}
            </h2>
          ) : (
            <span />
          )}
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}
