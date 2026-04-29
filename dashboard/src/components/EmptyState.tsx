export function EmptyState() {
  return (
    <section className="rounded-3xl border border-amber-300/20 bg-amber-300/10 p-6 text-amber-50">
      <h2 className="text-xl font-semibold">Dashboard data is not connected yet</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-amber-100/80">
        Add `SUPABASE_URL` and `SUPABASE_KEY` to the API environment, then ingest budget documents.
        The dashboard will automatically show county coverage, documents, and search results.
      </p>
    </section>
  );
}
