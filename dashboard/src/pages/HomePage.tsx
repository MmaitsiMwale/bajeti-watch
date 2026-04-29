import { getSummary } from "../api";
import { EmptyState } from "../components/EmptyState";
import { StatusCard } from "../components/StatusCard";
import { useAsync } from "../hooks/useAsync";

type HomePageProps = {
  onNavigate: (path: string) => void;
};

export function HomePage({ onNavigate }: HomePageProps) {
  const { data, error, loading } = useAsync(getSummary, []);

  if (loading) {
    return <p className="text-slate-300">Loading dashboard coverage...</p>;
  }

  if (error) {
    return <p className="rounded-2xl bg-red-500/10 p-5 text-red-100">Could not load dashboard data: {error}</p>;
  }

  if (!data || !data.configured) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-10">
      <section className="max-w-3xl">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-emerald-300">Public Budget Coverage</p>
        <h2 className="mt-4 text-4xl font-bold tracking-tight text-white sm:text-5xl">
          See which county budget documents are available.
        </h2>
        <p className="mt-4 text-lg leading-8 text-slate-300">
          Track ingested budget documents by county, year, and sector before asking deeper questions through WhatsApp.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatusCard hint="Uploaded budget documents" label="Documents" value={data.document_count} />
        <StatusCard hint="Counties represented" label="Counties" value={data.county_count} />
        <StatusCard hint="Most recent financial year" label="Latest Year" value={data.latest_year ?? "N/A"} />
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-white">County Coverage</h2>
            <p className="mt-1 text-sm text-slate-400">Open a county to see its available budget documents.</p>
          </div>
          <button className="rounded-full bg-white/10 px-4 py-2 text-sm text-slate-100" onClick={() => onNavigate("/search")} type="button">
            Search documents
          </button>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.counties.map((county) => (
            <button
              className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 text-left transition hover:-translate-y-1 hover:border-emerald-300/60"
              key={county.county}
              onClick={() => onNavigate(`/county/${encodeURIComponent(county.county)}`)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-xl font-semibold text-white">{county.county}</h3>
                <span className="rounded-full bg-emerald-300 px-3 py-1 text-xs font-semibold text-slate-950">
                  {county.document_count} docs
                </span>
              </div>
              <p className="mt-3 text-sm text-slate-400">Latest year: {county.latest_year ?? "Unknown"}</p>
              <p className="mt-4 line-clamp-2 text-sm text-slate-300">
                {county.sectors.length > 0 ? county.sectors.join(", ") : "No sectors tagged yet"}
              </p>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
