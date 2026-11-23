import { NavLink, Outlet } from "react-router-dom";
import { FilterBar } from "@/components/layout/FilterBar";

const links = [
  { to: "/presentation", label: "Presentation" },
  { to: "/", label: "Dashboard" },
  { to: "/map", label: "Map explorer" },
  { to: "/air-quality", label: "Air quality" },
  { to: "/land-cover", label: "Land cover" },
  { to: "/scenarios", label: "Land use contrasts" },
  { to: "/local-questions", label: "Local questions" },
  { to: "/relationships", label: "Relationships" },
  { to: "/projection", label: "Built-up projection" },
  { to: "/priority", label: "Priority" },
  { to: "/reports", label: "Reports" },
  { to: "/datasets", label: "Datasets" },
  { to: "/methodology", label: "Methodology" },
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-moss">
              Geospatial research platform
            </p>
            <h1 className="font-display text-2xl leading-tight">
              Air pollution and land-use impact
            </h1>
          </div>
          <p className="max-w-md text-sm text-stone-600">
            Delhi, NCT of Delhi. Associations are observational. Sample datasets
            are labeled and never presented as official measurements.
          </p>
        </div>
        <nav
          className="border-t border-stone-100 bg-stone-50"
          aria-label="Primary"
        >
          <div className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-2 py-2">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-full px-3 py-1.5 text-sm ${isActive ? "bg-ink text-white" : "text-stone-700 hover:bg-white"}`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        </nav>
        <FilterBar />
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
