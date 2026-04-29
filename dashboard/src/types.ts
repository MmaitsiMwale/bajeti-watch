export type CountySummary = {
  county: string;
  document_count: number;
  latest_year: string | null;
  sectors: string[];
};

export type DashboardSummary = {
  configured: boolean;
  document_count: number;
  county_count: number;
  latest_year: string | null;
  years: string[];
  counties: CountySummary[];
};

export type BudgetDocument = {
  id: string | null;
  title: string;
  county: string;
  financial_year: string | null;
  document_type: string | null;
  source_url: string | null;
  source_file: string | null;
  sectors: string[];
  ingested_at: string | null;
};

export type SearchResult = BudgetDocument & {
  snippet: string;
};
