export function AboutPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <p className="text-sm font-semibold uppercase tracking-[0.3em] text-emerald-300">About</p>
      <h2 className="text-4xl font-bold text-white">Budget transparency for every Kenyan citizen.</h2>
      <p className="text-lg leading-8 text-slate-300">
        Bajeti Watch turns county and national budget PDFs into searchable public information.
        Citizens can browse document coverage here or ask questions through WhatsApp without installing an app.
      </p>
      <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
        <h3 className="text-xl font-semibold text-white">How it works</h3>
        <ol className="mt-4 space-y-3 text-slate-300">
          <li>1. Budget PDFs are converted into clean Markdown.</li>
          <li>2. Documents are tagged with county, year, document type, and sectors.</li>
          <li>3. Supabase stores documents and searchable chunks.</li>
          <li>4. The dashboard and WhatsApp bot expose the same public budget knowledge.</li>
        </ol>
      </div>
    </div>
  );
}
