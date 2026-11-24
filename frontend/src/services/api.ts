export interface StatementMetadata {
  filename: string;
  portfolio_number?: string;
  portfolio_name?: string;
  valuation_date?: string;
  report_edited_date?: string;
  bank_name: string;
  report_currency: string;
  total_pages: number;
  detected_sections: string[];
  client_name?: string;
  client_reference?: string;
  relationship_type?: string;
  portfolio_previous_esg_rating?: string;
  portfolio_current_esg_rating?: string;
  portfolio_esg_previous?: string;
  portfolio_esg_current?: string;
  portfolio_esg_source_page?: number;
}

export interface AssetAllocationItem {
  investment_category: string;
  value_usd?: number;
  percentage?: number;
  raw_value: string;
  raw_percentage: string;
  source_page: number;
}

export interface CurrencyDetail {
  amount_in_thousands?: number;
  percentage?: number;
  raw_amount?: string;
  raw_pct?: string;
}

export interface CurrencyBreakdownItem {
  asset_class: string;
  total_in_thousands?: number;
  total_percentage?: number;
  currencies: Record<string, CurrencyDetail>;
  source_page: number;
  raw_text: string;
}

export interface HoldingItem {
  id: string;
  asset_category: string;
  units_nominal?: number;
  units_nominal_raw?: string;
  security_name: string;
  isin_secur_no?: string;
  yield_val?: number;
  duration?: string;
  rating?: string;
  net_avg_cost?: number;
  net_avg_cost_currency?: string;
  market_price?: number;
  market_price_currency?: string;
  market_price_date?: string;
  total_market_value?: number;
  market_value_currency?: string;
  accrued_interest?: number;
  accrued_interest_currency?: string;
  accrued_interest_usd?: number;
  value_in_usd?: number;
  percentage_of_total_assets?: number;
  source_page: number;
  raw_text: string;
}

export interface CurrentAccountItem {
  id: string;
  currency: string;
  amount?: number;
  account_name: string;
  account_number?: string;
  market_value?: number;
  market_value_usd?: number;
  percentage_assets?: number;
  source_page: number;
  raw_text: string;
}

export interface LoanItem {
  id: string;
  currency: string;
  amount?: number;
  description: string;
  loan_reference?: string;
  maturity_date?: string;
  interest_rate?: number;
  market_value?: number;
  accrued_interest?: number;
  usd_equivalent?: number;
  percentage_assets?: number;
  source_page: number;
  raw_text: string;
}

export interface NetAssetsSummaryData {
  assets_usd?: number;
  assets_pct?: number;
  accrued_interest_securities_usd?: number;
  accrued_interest_securities_pct?: number;
  net_accrued_int_deposits_loans_usd?: number;
  net_accrued_int_deposits_loans_pct?: number;
  total_assets_usd?: number;
  total_assets_pct?: number;
  commitments_usd?: number;
  source_page: number;
}

export interface ExchangeRateItem {
  base_currency: string;
  target_currency: string;
  rate: number;
  raw_text: string;
  source_page: number;
}

export interface PerformanceRow {
  period: string;
  performance_pct?: number;
  cumulative_performance_pct?: number;
  end_of_period_assets?: number;
  period_deposits_withdrawals?: number;
  change_in_total_assets?: number;
  net_income?: number;
  return_on_net_income_pct?: number;
  is_initial_row: boolean;
  is_total_row: boolean;
  row_type?: string;
  source_page: number;
  raw_text: string;
}

export interface CommentsDisclosuresData {
  general_information: string;
  product_risk_classification: string;
  acknowledgement_of_assets: string;
  disclaimers: string[];
  source_pages: number[];
}

export interface ValidationCheck {
  category: string;
  name: string;
  level: "PASS" | "WARNING" | "FAIL";
  message: string;
  details: Record<string, any>;
}

export interface PortfolioSummaryPerformance {
  reporting_period?: string;
  initial_assets?: number;
  total_incoming_securities?: number;
  total_outgoing_securities?: number;
  total_incoming_cash?: number;
  total_outgoing_cash?: number;
  total_inc_out_cash_sec?: number;
  change_in_total_assets?: number;
  valuation_date?: string;
  ending_assets?: number;
  number_of_days?: number;
  performance_twr_pct?: number;
  portfolio_esg_previous?: string;
  portfolio_esg_current?: string;
  portfolio_esg_source_page?: number;
  portfolio_previous_esg_rating?: string;
  portfolio_current_esg_rating?: string;
  source_page: number;
  raw_values: Record<string, string>;
}

export interface StatementExtractionResult {
  metadata: StatementMetadata;
  portfolio_summary_performance?: PortfolioSummaryPerformance;
  asset_allocation: AssetAllocationItem[];
  currency_breakdown: CurrencyBreakdownItem[];
  holdings: HoldingItem[];
  current_accounts: CurrentAccountItem[];
  loans: LoanItem[];
  net_assets_summary?: NetAssetsSummaryData;
  exchange_rates: ExchangeRateItem[];
  monthly_performance: PerformanceRow[];
  annual_performance: PerformanceRow[];
  comments_disclosures: CommentsDisclosuresData;
  validation_checks: ValidationCheck[];
  excel_path?: string;
}

export interface ExtractionJobStatus {
  job_id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  phase: string;
  progress_percentage: number;
  total_files: number;
  processed_files: number;
  current_file?: string;
  error_message?: string;
  results: StatementExtractionResult[];
  zip_path?: string;
}

export interface JobFilesResponse {
  job_id: string;
  files: {
    file_id: number;
    filename: string;
    portfolio_number?: string;
    valuation_date?: string;
    pages: number;
    holdings_count: number;
    download_url: string;
  }[];
  zip_available: boolean;
  download_all_url: string;
}

const API_BASE = "/api";

export async function uploadStatements(files: File[]): Promise<{ job_id: string }> {
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }
  const res = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}


export async function getJobStatus(jobId: string): Promise<ExtractionJobStatus> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch job status for ${jobId}`);
  }
  return res.json();
}

export async function getJobFiles(jobId: string): Promise<JobFilesResponse> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/files`);
  if (!res.ok) {
    throw new Error(`Failed to fetch files for ${jobId}`);
  }
  return res.json();
}

export async function deleteJob(jobId: string): Promise<void> {
  await fetch(`${API_BASE}/jobs/${jobId}`, { method: "DELETE" });
}
