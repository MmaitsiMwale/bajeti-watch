import type { ReactNode } from "react";

type LayoutProps = {
  children: ReactNode;
  currentPath: string;
  onNavigate: (path: string) => void;
};

const navItems = [
  { label: "Overview", path: "/" },
  { label: "Search", path: "/search" },
  { label: "About", path: "/about" },
];

export function Layout({ children, currentPath, onNavigate }: LayoutProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 bg-slate-950/90">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <button className="text-left" onClick={() => onNavigate("/")} type="button">
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-emerald-300">Bajeti Watch</p>
            <h1 className="text-2xl font-bold tracking-tight">Kenya Budget Dashboard</h1>
          </button>
          <nav className="flex gap-2">
            {navItems.map((item) => {
              const active = currentPath === item.path;
              return (
                <button
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    active ? "bg-emerald-400 text-slate-950" : "text-slate-300 hover:bg-white/10"
                  }`}
                  key={item.path}
                  onClick={() => onNavigate(item.path)}
                  type="button"
                >
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
