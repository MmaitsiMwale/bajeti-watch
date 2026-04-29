import { FormEvent, useState } from "react";

import { searchDocuments } from "../api";
import { EmptyState } from "../components/EmptyState";
import type { SearchResult } from "../types";

type SearchState = {
  configured: boolean;
  results: SearchResult[];
};

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await searchDocuments(trimmed);
      setState({ configured: response.configured, results: response.results });
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-emerald-300">Search</p>
        <h2 className="mt-3 text-4xl font-bold text-white">Find budget lines across documents.</h2>
        <p className="mt-3 max-w-2xl text-slate-300">
          Search by county, sector, project, or allocation amount. Results come from uploaded Supabase documents.
        </p>
      </section>

      <form className="flex flex-col gap-3 rounded-3xl border border-white/10 bg-white/[0.04] p-4 sm:flex-row" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none ring-emerald-300/40 placeholder:text-slate-500 focus:ring-4"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Try roads, health, Kisumu, 800,000,000..."
          type="search"
          value={query}
        />
        <button className="rounded-2xl bg-emerald-300 px-6 py-3 font-semibold text-slate-950 disabled:opacity-60" disabled={loading} type="submit">
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error ? <p className="rounded-2xl bg-red-500/10 p-5 text-red-100">Could not search documents: {error}</p> : null}
      {state && !state.configured ? <EmptyState /> : null}
      {state?.configured ? (
        <section className="space-y-4">
          <h3 className="text-xl font-semibold text-white">{state.results.length} result(s)</h3>
          {state.results.map((result) => (
            <article className="rounded-2xl border border-white/10 bg-white/[0.04] p-5" key={result.id ?? result.source_file}>
              <h4 className="text-lg font-semibold text-white">{result.title}</h4>
              <p className="mt-1 text-sm text-slate-400">
                {result.county} {result.financial_year ? `| ${result.financial_year}` : ""}
              </p>
              <p className="mt-4 text-sm leading-6 text-slate-300">{result.snippet || "Matched this document title."}</p>
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
