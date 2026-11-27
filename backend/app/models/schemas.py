from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal

class CurrencyDetail(BaseModel):
    amount_in_thousands: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    raw_amount: Optional[str] = None
    raw_pct: Optional[str] = None

class CurrencyBreakdownItem(BaseModel):
    asset_class: str
    total_in_thousands: Optional[Decimal] = None
    total_percentage: Optional[Decimal] = None
    unit_scale: str = "THOUSANDS"  # "THOUSANDS" or "UNITS"
    detected_currencies: List[str] = Field(default_factory=list)
    currencies: Dict[str, CurrencyDetail] = Field(default_factory=dict)
    source_page: int
    raw_text: str

class AssetAllocationItem(BaseModel):
    investment_category: str
    value_usd: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    raw_value: str
    raw_percentage: str
    source_page: int

class PortfolioSummaryPerformance(BaseModel):
    reporting_period: Optional[str] = None
    initial_assets: Optional[Decimal] = None
    total_incoming_securities: Optional[Decimal] = None
    total_outgoing_securities: Optional[Decimal] = None
    total_incoming_cash: Optional[Decimal] = None
    total_outgoing_cash: Optional[Decimal] = None
    total_inc_out_cash_sec: Optional[Decimal] = None
    change_in_total_assets: Optional[Decimal] = None
    valuation_date: Optional[str] = None
    ending_assets: Optional[Decimal] = None
    number_of_days: Optional[int] = None
    performance_twr_pct: Optional[Decimal] = None
    portfolio_esg_previous: Optional[str] = None
    portfolio_esg_current: Optional[str] = None
    portfolio_esg_source_page: Optional[int] = None
    portfolio_esg_provenance: Optional[str] = "NOT_PRESENT"
    portfolio_previous_esg_rating: Optional[str] = None
    portfolio_current_esg_rating: Optional[str] = None
    source_page: int = 1
    raw_values: Dict[str, str] = Field(default_factory=dict)

class HoldingItem(BaseModel):
    id: str
    asset_category: str
    units_nominal: Optional[Decimal] = None
    units_nominal_raw: Optional[str] = None
    security_name: str
    isin_secur_no: Optional[str] = None
    yield_val: Optional[Decimal] = None
    yield_state: str = "SOURCE_BLANK"
    duration: Optional[str] = None
    rating: Optional[str] = None
    net_avg_cost: Optional[Decimal] = None
    net_avg_cost_currency: Optional[str] = None
    market_price: Optional[Decimal] = None
    market_price_state: str = "SOURCE_BLANK"
    price_marker: Optional[str] = None
    market_price_currency: Optional[str] = None
    market_price_date: Optional[str] = None
    total_market_value: Optional[Decimal] = None
    total_market_value_state: str = "SOURCE_BLANK"
    market_value_currency: Optional[str] = None
    accrued_interest: Optional[Decimal] = None
    accrued_interest_currency: Optional[str] = None
    accrued_interest_usd: Optional[Decimal] = None
    value_in_usd: Optional[Decimal] = None
    value_in_usd_state: str = "SOURCE_BLANK"
    percentage_of_total_assets: Optional[Decimal] = None
    percentage_state: str = "SOURCE_BLANK"
    calculated_percentage_of_assets: Optional[Decimal] = None
    previous_esg_rating: Optional[str] = None
    current_esg_rating: Optional[str] = None
    esg_rating_previous: Optional[str] = None
    esg_rating_current: Optional[str] = None
    raw_identifier: Optional[str] = None
    identifier_status: str = "PASS"
    identifier_provenance: Optional[str] = None
    identifier_confidence: Optional[float] = None
    header_confidence: str = "HIGH"
    unassigned_tokens: List[str] = Field(default_factory=list)
    source_page: int
    bbox: List[float] = Field(default_factory=list)
    raw_text: str

class CurrentAccountItem(BaseModel):
    id: str
    currency: str
    amount: Optional[Decimal] = None
    account_name: str
    account_number: Optional[str] = None
    market_value: Optional[Decimal] = None
    market_value_usd: Optional[Decimal] = None
    percentage_assets: Optional[Decimal] = None
    source_page: int
    raw_text: str

class LoanItem(BaseModel):
    id: str
    currency: str
    amount: Optional[Decimal] = None
    description: str
    loan_reference: Optional[str] = None
    maturity_date: Optional[str] = None
    interest_rate: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    accrued_interest: Optional[Decimal] = None
    usd_equivalent: Optional[Decimal] = None
    percentage_assets: Optional[Decimal] = None
    source_page: int
    raw_text: str

class ExchangeRateItem(BaseModel):
    base_currency: str = "USD"
    target_currency: str
    rate: Decimal
    raw_text: str
    source_page: int

class NetAssetsSummaryData(BaseModel):
    assets_usd: Optional[Decimal] = None
    assets_pct: Optional[Decimal] = None
    accrued_interest_securities_usd: Optional[Decimal] = None
    accrued_interest_securities_pct: Optional[Decimal] = None
    net_accrued_int_deposits_loans_usd: Optional[Decimal] = None
    net_accrued_int_deposits_loans_pct: Optional[Decimal] = None
    total_assets_usd: Optional[Decimal] = None
    total_assets_pct: Optional[Decimal] = None
    commitments_usd: Optional[Decimal] = None
    source_page: int
    raw_text: str

class PerformanceRow(BaseModel):
    period: str
    performance_pct: Optional[Decimal] = None
    cumulative_performance_pct: Optional[Decimal] = None
    end_of_period_assets: Optional[Decimal] = None
    period_deposits_withdrawals: Optional[Decimal] = None
    change_in_total_assets: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    return_on_net_income_pct: Optional[Decimal] = None
    is_initial_row: bool = False
    is_total_row: bool = False
    row_type: Optional[str] = None
    source_page: int
    raw_text: str

class CommentsDisclosuresData(BaseModel):
    general_information: str = ""
    product_risk_classification: str = ""
    acknowledgement_of_assets: str = ""
    disclaimers: List[str] = Field(default_factory=list)
    source_pages: List[int] = Field(default_factory=list)
    general_info_pages: List[int] = Field(default_factory=list)
    prc_pages: List[int] = Field(default_factory=list)
    ack_pages: List[int] = Field(default_factory=list)

class RawPageData(BaseModel):
    page_number: int
    section_name: str
    rotation: int
    width: float
    height: float
    line_count: int
    word_count: int
    text: str
    word_coordinates: List[Dict[str, Any]] = Field(default_factory=list)
    page_type: str = "TEXT_BASED"
    ocr_applied: bool = False
    ocr_confidence: Optional[float] = None

class UnmappedContentItem(BaseModel):
    page_number: int
    raw_text: str
    bbox: List[float] = Field(default_factory=list)
    reason: str

class ValidationCheck(BaseModel):
    category: str
    name: str
    level: str  # "PASS", "WARNING", "FAIL"
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

class StatementMetadata(BaseModel):
    filename: str
    portfolio_number: Optional[str] = None
    portfolio_number_extracted: Optional[str] = None
    portfolio_number_fallback: Optional[str] = None
    portfolio_identifier_source: str = "EXTRACTED_FROM_PDF"  # "EXTRACTED_FROM_PDF" or "INFERRED_FROM_FILENAME"
    portfolio_name: Optional[str] = None
    valuation_date: Optional[str] = None
    report_edited_date: Optional[str] = None
    bank_name: str = "NOT_STATED"
    institution_provenance: str = "NOT_PRESENT"  # EXTRACTED, INFERRED, NOT_PRESENT
    report_currency: str = "USD"
    reporting_period: Optional[str] = None
    total_pages: int
    detected_sections: List[str] = Field(default_factory=list)
    client_name: Optional[str] = None
    client_reference: Optional[str] = None
    relationship_type: Optional[str] = None
    portfolio_previous_esg_rating: Optional[str] = None
    portfolio_current_esg_rating: Optional[str] = None
    portfolio_esg_previous: Optional[str] = None
    portfolio_esg_current: Optional[str] = None
    portfolio_esg_source_page: Optional[int] = None
    portfolio_esg_provenance: Optional[str] = "NOT_PRESENT"

class StatementExtractionResult(BaseModel):
    metadata: StatementMetadata
    portfolio_summary_performance: Optional[PortfolioSummaryPerformance] = None
    asset_allocation: List[AssetAllocationItem] = Field(default_factory=list)
    currency_breakdown: List[CurrencyBreakdownItem] = Field(default_factory=list)
    holdings: List[HoldingItem] = Field(default_factory=list)
    current_accounts: List[CurrentAccountItem] = Field(default_factory=list)
    loans: List[LoanItem] = Field(default_factory=list)
    net_assets_summary: Optional[NetAssetsSummaryData] = None
    exchange_rates: List[ExchangeRateItem] = Field(default_factory=list)
    monthly_performance: List[PerformanceRow] = Field(default_factory=list)
    annual_performance: List[PerformanceRow] = Field(default_factory=list)
    comments_disclosures: CommentsDisclosuresData = Field(default_factory=CommentsDisclosuresData)
    unmapped_content: List[UnmappedContentItem] = Field(default_factory=list)
    raw_pages: List[RawPageData] = Field(default_factory=list)
    validation_checks: List[ValidationCheck] = Field(default_factory=list)
    section_confidence: Dict[str, str] = Field(default_factory=dict)
    detected_column_maps: Dict[str, Any] = Field(default_factory=dict)
    excel_path: Optional[str] = None

from enum import Enum

class JobLifecycleState(str, Enum):
    QUEUED = "QUEUED"
    UPLOADING = "UPLOADING"
    INSPECTING = "INSPECTING"
    CLASSIFYING = "CLASSIFYING"
    EXTRACTING = "EXTRACTING"
    NORMALIZING = "NORMALIZING"
    VALIDATING = "VALIDATING"
    GENERATING_EXCEL = "GENERATING_EXCEL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ExtractionJobStatus(BaseModel):
    job_id: str
    status: str  # One of JobLifecycleState
    phase: str
    stage: str = "QUEUED"
    progress_percentage: int
    total_files: int
    processed_files: int
    current_file: Optional[str] = None
    total_pages: Optional[int] = None
    processed_pages: Optional[int] = None
    accepted_files: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    results: List[StatementExtractionResult] = Field(default_factory=list)
    zip_path: Optional[str] = None
    download_url: Optional[str] = None
