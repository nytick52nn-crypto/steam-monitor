import { cn } from "../../utils/cn";

export function Card({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-panel-border bg-panel-card p-4 shadow-lg",
        className
      )}
    >
      {children}
    </div>
  );
}
