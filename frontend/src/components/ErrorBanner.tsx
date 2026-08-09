export function ErrorBanner({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      role="alert"
      className="mb-6 rounded-lg border border-amber-800/50 bg-amber-950/20 p-4 text-sm text-amber-200"
    >
      <div className="font-medium text-amber-100">{title}</div>
      <div className="mt-1 text-amber-200/90">{children}</div>
    </div>
  );
}
