import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t bg-muted/30">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 py-4 text-sm text-muted-foreground sm:flex-row sm:px-6 lg:px-8">
        <p>Active Alpha &copy; {new Date().getFullYear()}</p>
        <Link
          href="/docs"
          className="underline-offset-4 transition-colors hover:text-foreground hover:underline"
        >
          API Docs
        </Link>
      </div>
    </footer>
  );
}
