import { getDocuments } from "../api";
import { DocumentList } from "../components/DocumentList";
import { EmptyState } from "../components/EmptyState";
import { useAsync } from "../hooks/useAsync";

type CountyPageProps = {
  county: string;
  onNavigate: (path: string) => void;
};

export function CountyPage({ county, onNavigate }: CountyPageProps) {
  const decodedCounty = decodeURIComponent(county);
  const { data, error, loading } = useAsync(() => getDocuments(decodedCounty), [decodedCounty]);

  return (
    <div className="space-y-8">
      <button className="text-sm font-medium text-emerald-300 hover:text-emerald-200" onClick={() => onNavigate("/")} type="button">
        Back to overview
      </button>

      <section>
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-emerald-300">County Detail</p>
        <h2 className="mt-3 text-4xl font-bold text-white">{decodedCounty}</h2>
        <p className="mt-3 max-w-2xl text-slate-300">
          Budget documents and sectors currently available for this county.
        </p>
      </section>

      {loading ? <p className="text-slate-300">Loading {decodedCounty} documents...</p> : null}
      {error ? <p className="rounded-2xl bg-red-500/10 p-5 text-red-100">Could not load county data: {error}</p> : null}
      {data && !data.configured ? <EmptyState /> : null}
      {data?.configured ? <DocumentList documents={data.documents} /> : null}
    </div>
  );
}
