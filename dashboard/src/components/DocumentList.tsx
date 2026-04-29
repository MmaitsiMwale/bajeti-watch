import type { BudgetDocument } from "../types";

type DocumentListProps = {
  documents: BudgetDocument[];
};

export function DocumentList({ documents }: DocumentListProps) {
  if (documents.length === 0) {
    return <p className="rounded-2xl bg-white/[0.04] p-5 text-slate-400">No documents found.</p>;
  }

  return (
    <div className="grid gap-4">
      {documents.map((document) => (
        <article className="rounded-2xl border border-white/10 bg-white/[0.04] p-5" key={document.id ?? document.source_file}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">{document.title}</h3>
              <p className="mt-1 text-sm text-slate-400">
                {document.county} {document.financial_year ? `| ${document.financial_year}` : ""}
              </p>
            </div>
            {document.source_url ? (
              <a className="text-sm font-medium text-emerald-300 hover:text-emerald-200" href={document.source_url}>
                Source PDF
              </a>
            ) : null}
          </div>
          {document.sectors.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {document.sectors.map((sector) => (
                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300" key={sector}>
                  {sector}
                </span>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}
