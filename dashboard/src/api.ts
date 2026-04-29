import type { BudgetDocument, DashboardSummary, SearchResult } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getSummary(): Promise<DashboardSummary> {
  return getJson<DashboardSummary>("/dashboard/summary");
}

export async function getDocuments(county?: string): Promise<{
  configured: boolean;
  documents: BudgetDocument[];
}> {
  const params = new URLSearchParams();
  if (county) {
    params.set("county", county);
  }
  const suffix = params.toString() ? `?${params}` : "";
  return getJson(`/dashboard/documents${suffix}`);
}

export async function searchDocuments(query: string): Promise<{
  configured: boolean;
  query: string;
  results: SearchResult[];
}> {
  const params = new URLSearchParams({ q: query });
  return getJson(`/dashboard/search?${params}`);
}
