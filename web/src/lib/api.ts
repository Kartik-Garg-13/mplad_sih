export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8020";

export type FlagRow = {
  work_id: string;
  state: string | null;
  district_raw: string | null;
  implementing_agency: string | null;
  mp_name: string | null;
  category: string | null;
  description: string | null;
  sanction_amount: number | null;
  recommended_amount: number | null;
  work_status: string | null;
  financial_year: string | null;
  n_flags: number;
  detectors: string[];
  has_tier_a: boolean;
  has_tier_b: boolean;
};

export type FlagsResponse = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: FlagRow[];
};

export type Stats = {
  total_works: number;
  total_flags: number;
  flagged_works: number;
  flagged_share: number;
  by_detector: { detector: string; tier: string; n: number }[];
  n_detectors: number;
};

export type Meta = {
  states: string[];
  categories: string[];
  detectors: string[];
};

export type Flag = { detector: string; tier: string; evidence: string };

export type Payment = {
  expenditure_date: string | null;
  vendor_name: string | null;
  payment_status: string | null;
  amount: number | null;
};

export type Override = { work_id: string; note: string | null; reviewed_at: string } | null;

export type WorkDetail = {
  work: Record<string, unknown> & { work_id: string };
  flags: Flag[];
  payments: Payment[];
  override: Override;
};

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function getStats() {
  return apiFetch<Stats>("/api/stats");
}

export function getMeta() {
  return apiFetch<Meta>("/api/meta");
}

export type Detector = {
  id: string;
  tier: "A" | "B";
  title: string;
  description: string;
  benign_explanation: string;
};

export type DetectorsResponse = { detectors: Detector[] };

export function getDetectors() {
  return apiFetch<DetectorsResponse>("/api/detectors");
}

export type Provenance = {
  source_name: string;
  source_url: string;
  houses_covered: string;
  snapshot_date: string;
  financial_year_earliest: string | null;
  financial_year_latest: string | null;
  n_works: number;
  n_expenditure_records: number;
  n_allocated_records: number;
  n_states: number;
  n_mps: number;
  n_agencies: number;
  quantity_coverage: number;
  image_evidence_coverage: number;
  description_corruption_rate: number;
};

export function getProvenance() {
  return apiFetch<Provenance>("/api/provenance");
}

export function getFlags(params: Record<string, string | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }
  return apiFetch<FlagsResponse>(`/api/flags?${qs.toString()}`);
}

export function getWorkDetail(workId: string) {
  return apiFetch<WorkDetail>(`/api/works/${encodeURIComponent(workId).replace(/%2F/g, "/")}`);
}

export type PeerDistribution = {
  n: number;
  median: number;
  bucket_edges: number[];
  bucket_counts: number[];
  own_value: number;
  own_bucket: number;
};

export type WorkPeersResponse = {
  work_id: string;
  // Keyed by detector id ("B1", "B3", ...) — a detector with no eligible
  // peer group for this specific work (its own group never reached the
  // n>=30 floor) simply has no key here, the same abstention Tier B
  // itself applies.
  peers: Record<string, PeerDistribution>;
};

export function getWorkPeers(workId: string) {
  return apiFetch<WorkPeersResponse>(`/api/works/${encodeURIComponent(workId).replace(/%2F/g, "/")}/peers`);
}

export async function addOverride(workId: string, note: string | null): Promise<Override> {
  const path = `/api/works/${encodeURIComponent(workId).replace(/%2F/g, "/")}/override`;
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return res.json();
}

export async function removeOverride(workId: string): Promise<void> {
  const path = `/api/works/${encodeURIComponent(workId).replace(/%2F/g, "/")}/override`;
  const res = await fetch(`${API_URL}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
}

export type OverrideWorkSummary = {
  work_id: string;
  state: string | null;
  district_raw: string | null;
  implementing_agency: string | null;
  mp_name: string | null;
  category: string | null;
  description: string | null;
  sanction_amount: number | null;
  recommended_amount: number | null;
  work_status: string | null;
  financial_year: string | null;
};

export type OverrideEntry = {
  work_id: string;
  note: string | null;
  reviewed_at: string;
  // null when the work has since left the corpus (e.g. its source dataset
  // was removed) — the override itself is never dropped just because the
  // work it referred to did.
  work: OverrideWorkSummary | null;
};

export type OverridesResponse = { overrides: OverrideEntry[] };

export function getOverrides(params: { search?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  const query = qs.toString();
  return apiFetch<OverridesResponse>(`/api/overrides${query ? `?${query}` : ""}`);
}

/** Works with zero flags. `include_unsanctioned` defaults to false server-side
 * — see the endpoint's own note on why never-evaluated works aren't counted
 * as "clean" by default. */
export type UnflaggedResponse = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: OverrideWorkSummary[];
};

export function getUnflagged(params: Record<string, string | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }
  return apiFetch<UnflaggedResponse>(`/api/unflagged?${qs.toString()}`);
}

/** Not a fetch — a plain URL for an `<a>` tag, so the browser handles the
 * download natively (filename, save dialog) instead of the app buffering
 * a CSV blob in memory just to hand it back to the browser anyway. */
export function flagsExportCsvUrl(params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }
  return `${API_URL}/api/flags/export.csv?${qs.toString()}`;
}

export type AgencyRow = {
  implementing_agency: string;
  n_works: number;
  total_value: number;
  n_mps: number;
  n_states: number;
  value_per_work: number;
  is_thin_file: boolean;
  is_cross_state: boolean;
};

export type AgenciesResponse = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: AgencyRow[];
};

export type AgencyDetail = {
  agency: AgencyRow & { community: number | null };
  states: string[];
  mps: { mp_name: string; n_works: number; total_value: number }[];
  vendors: { vendor_name: string; n_payments: number; total_value: number }[];
};

export type GraphNode = { id: string; kind: "mp" | "agency"; label: string; community: number | null };
export type GraphEdge = { source: string; target: string; n_works: number; total_value: number };
export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };

export function getAgencies(params: Record<string, string | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }
  return apiFetch<AgenciesResponse>(`/api/agencies?${qs.toString()}`);
}

export function getAgencyDetail(agency: string) {
  return apiFetch<AgencyDetail>(`/api/agencies/${encodeURIComponent(agency).replace(/%2F/g, "/")}`);
}

export function getMpAgencyGraph(minValue: number) {
  return apiFetch<GraphData>(`/api/graph/mp-agency?min_value=${minValue}`);
}

export type StallModelMetrics = {
  n_train: number;
  n_test: number;
  positive_rate_train: number;
  positive_rate_test: number;
  pr_auc: number;
  roc_auc: number;
  calibration_mean_predicted: number[];
  calibration_fraction_positive: number[];
};

export type StallModelResponse = {
  metrics: StallModelMetrics;
  feature_importances: { feature: string; importance: number }[];
};

export type AtRiskRow = {
  work_id: string;
  stall_risk: number;
  days_open: number;
  p75_days: number;
  state: string | null;
  district_raw: string | null;
  implementing_agency: string | null;
  mp_name: string | null;
  category: string | null;
  description: string | null;
  sanction_amount: number | null;
};

export type AtRiskResponse = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: AtRiskRow[];
};

export function getStallModelMetrics() {
  return apiFetch<StallModelResponse>("/api/model/stall-risk");
}

export function getAtRisk(params: Record<string, string | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }
  return apiFetch<AtRiskResponse>(`/api/at-risk?${qs.toString()}`);
}

export type ConstituencyRow = {
  state: string;
  constituency: string;
  mp_name: string | null;
  n_sanctioned: number;
  n_completed: number;
  completion_rate: number | null;
  median_days_to_complete: number | null;
  total_sanctioned: number;
  total_expended: number;
  allocated_amount: number;
  fund_utilisation: number | null;
  unspent_balance: number;
  dominant_category: string | null;
  dominant_category_share: number | null;
};

export type ConstituenciesResponse = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: ConstituencyRow[];
};

export type ValidationSyntheticPerType = {
  injected_type: string;
  target_detector: string;
  n_injected: number;
  recall_target_detector: number;
  recall_any_detector: number;
};
export type ValidationSyntheticAtK = { k: number; precision_at_k: number; recall_at_k: number };
export type ValidationStability = {
  detector: string;
  baseline_n_flagged: number;
  n_bootstrap: number;
  mean_jaccard_vs_baseline: number;
  min_jaccard_vs_baseline: number;
  max_jaccard_vs_baseline: number;
};
export type ValidationKnownCase = {
  source: string;
  description: string;
  state: string;
  searched_agency_substring: string | null;
  matched: boolean;
  reason: string;
};
export type ValidationAdjudicationCluster = {
  cluster: string;
  state: string;
  mp_name: string;
  implementing_agency: string;
  category: string;
  n_works_in_top50: number;
  classification: "plausibly_irregular" | "benign_explained" | "undecided";
  note: string;
};
export type Validation = {
  synthetic_injection: { per_type: ValidationSyntheticPerType[]; at_k: ValidationSyntheticAtK[] };
  stability: ValidationStability[];
  known_cases: ValidationKnownCase[];
  adjudication: { clusters: ValidationAdjudicationCluster[]; n_reviewed: number };
};

export function getValidation() {
  return apiFetch<Validation>("/api/validation");
}

export function getConstituencies(params: Record<string, string | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) qs.set(k, v);
  }
  return apiFetch<ConstituenciesResponse>(`/api/constituencies?${qs.toString()}`);
}

export type Overview = {
  by_state: { state: string; n_flagged: number }[];
  by_year: { financial_year: string; n_works: number; n_flagged: number }[];
  by_category: { category: string; n_flagged: number }[];
  tier_composition: { bucket: "both" | "tier_a_only" | "tier_b_only"; n: number }[];
};

export function getOverview() {
  return apiFetch<Overview>("/api/overview");
}

export type SearchWorkHit = {
  work_id: string;
  description: string | null;
  state: string | null;
  mp_name: string | null;
  implementing_agency: string | null;
  sanction_amount: number | null;
};
export type SearchAgencyHit = { implementing_agency: string; n_works: number; total_value: number };
export type SearchConstituencyHit = { state: string; constituency: string; mp_name: string | null; n_sanctioned: number };
export type SearchResults = {
  query: string;
  works: SearchWorkHit[];
  n_works: number;
  agencies: SearchAgencyHit[];
  n_agencies: number;
  constituencies: SearchConstituencyHit[];
  n_constituencies: number;
};

export function search(q: string) {
  return apiFetch<SearchResults>(`/api/search?q=${encodeURIComponent(q)}`);
}

export type DatasetStage = {
  key: string;
  label: string;
  example: string;
  unlocks: string;
  required: boolean;
};

export type DatasetSource = {
  key: string;
  label: string;
  house: string | null;
  term: string | null;
  builtin: boolean;
  created_at: string | null;
  note: string | null;
  files: Record<string, string>;
  row_counts?: Record<string, number>;
  n_works: number;
  n_flagged: number;
};

export type RebuildJob = {
  id: string;
  reason: string;
  status: "running" | "done" | "error";
  step: number;
  step_label: string;
  total_steps: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type DatasetsResponse = {
  sources: DatasetSource[];
  stages: DatasetStage[];
  rebuild: RebuildJob | null;
};

export function getDatasets() {
  return apiFetch<DatasetsResponse>("/api/datasets");
}

export function getRebuildJob(jobId: string) {
  return apiFetch<RebuildJob>(`/api/datasets/jobs/${jobId}`);
}

export type CreateDatasetResult = { batch: DatasetSource & { row_counts: Record<string, number> }; job: RebuildJob };

async function parseApiError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // fall through to a generic message below
  }
  return `Request failed (${res.status})`;
}

export async function createDataset(form: FormData): Promise<CreateDatasetResult> {
  const res = await fetch(`${API_URL}/api/datasets`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseApiError(res));
  return res.json();
}

export async function deleteDataset(key: string): Promise<{ removed: string; job: RebuildJob }> {
  const res = await fetch(`${API_URL}/api/datasets/${encodeURIComponent(key)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseApiError(res));
  return res.json();
}
