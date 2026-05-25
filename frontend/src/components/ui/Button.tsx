import { cn } from "../../utils/cn";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: Props) {
  const variants = {
    primary: "bg-panel-accent hover:bg-blue-600 text-white",
    secondary: "bg-panel-card border border-panel-border hover:bg-slate-700",
    ghost: "hover:bg-panel-card text-slate-300",
    danger: "bg-panel-danger/20 text-panel-danger hover:bg-panel-danger/30",
  };
  const sizes = { sm: "px-2 py-1 text-xs", md: "px-4 py-2 text-sm" };
  return (
    <button
      className={cn(
        "rounded-lg font-medium transition disabled:opacity-50",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
