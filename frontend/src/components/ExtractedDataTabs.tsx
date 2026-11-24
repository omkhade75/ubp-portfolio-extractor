import React, { useState } from "react";
import {
  FileText,
  PieChart,
  Coins,
  Layers,
  Wallet,
  Landmark,
  ArrowLeftRight,
  TrendingUp,
  Calendar,
  MessageSquare,
  ShieldCheck,
  Scale
} from "lucide-react";
import { StatementExtractionResult } from "../services/api";
import { DataTable, ColumnDef } from "./DataTable";

interface ExtractedDataTabsProps {
  results: StatementExtractionResult[];
  activeResultIndex: number;
  onSelectResultIndex: (idx: number) => void;
}

export const ExtractedDataTabs: React.FC<ExtractedDataTabsProps> = ({
  results,
  activeResultIndex,
  onSelectResultIndex,
}) => {
  const [activeTab, setActiveTab] = useState("holdings");

  if (results.length === 0) return null;
  const current = results[activeResultIndex] || results[0];
  const meta = current.metadata;

  const toNum = (val: any): number | null => {
    if (val === undefined || val === null || val === "") return null;
    if (typeof val === "number") return isNaN(val) ? null : val;
    const cleaned = String(val).replace(/’/g, "").replace(/'/g, "").replace(/,/g, "").trim();
    const n = parseFloat(cleaned);
    return isNaN(n) ? null : n;
  };

  const formatAmount = (val?: any) => {
    const n = toNum(val);
    if (n === null) return "—";
    return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatPct = (val?: any) => {
    const n = toNum(val);
    if (n === null) return "—";
    return `${n.toFixed(2)}%`;
  };

  const formatInteger = (val?: any) => {
    const n = toNum(val);
    if (n === null) return "—";
    return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  };

  const formatRate = (val?: any) => {
    const n = toNum(val);
    if (n === null) return String(val || "—");
    return n.toFixed(8);
  };

  const tabs = [
    { id: "overview", label: "Portfolio Overview", icon: FileText, count: null },
    { id: "allocation", label: "Asset Allocation", icon: PieChart, count: current.asset_allocation?.length },
    { id: "currencies", label: "Currency Breakdown", icon: Coins, count: current.currency_breakdown?.length },
    { id: "holdings", label: "Holdings", icon: Layers, count: current.holdings?.length },
    { id: "accounts", label: "Current Accounts", icon: Wallet, count: current.current_accounts?.length },
    { id: "loans", label: "Loans", icon: Landmark, count: current.loans?.length },
    { id: "transactions", label: "Transactions", icon: ArrowLeftRight, count: null },
    { id: "summary", label: "Net Assets Summary", icon: Scale, count: null },
    { id: "rates", label: "Exchange Rates", icon: Coins, count: current.exchange_rates?.length },
    { id: "monthly", label: "Monthly Performance", icon: TrendingUp, count: current.monthly_performance?.length },
    { id: "annual", label: "Annual Performance", icon: Calendar, count: current.annual_performance?.length },
    { id: "comments", label: "Comments & Disclosures", icon: MessageSquare, count: null },
    { id: "validation", label: "Validation Report", icon: ShieldCheck, count: current.validation_checks?.length },
  ];

  return (
    <div className="space-y-4 my-6">
      {/* Top Statement Selector Bar */}
      <div className="bg-white p-3.5 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-700">Active Statement:</label>
          <select
            value={activeResultIndex}
            onChange={(e) => onSelectResultIndex(Number(e.target.value))}
            className="text-xs font-medium bg-slate-50 border border-slate-300 rounded px-2.5 py-1 text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
          >
            {results.map((r, idx) => (
              <option key={idx} value={idx}>
                {r.metadata.filename} (Portfolio: {r.metadata.portfolio_number || "Pending"} | {r.metadata.valuation_date})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-500 font-mono">
          <span>Pages: <b>{meta.total_pages}</b></span>
          <span>Currency: <b>{meta.report_currency}</b></span>
          <span>Edited: <b>{meta.report_edited_date}</b></span>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-slate-200 pb-1 scrollbar-none">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap transition border-b-2 ${
                isActive
                  ? "border-slate-900 text-slate-900 bg-white shadow-2xs font-semibold"
                  : "border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100/60"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.count !== null && (
                <span
                  className={`ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                    isActive ? "bg-slate-200 text-slate-900" : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content Panels */}
      <div>
        {/* 1. Overview */}
        {activeTab === "overview" && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
              <h3 className="text-sm font-semibold text-slate-800">Portfolio Header & Account Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-1.5">
                  <p className="flex justify-between">
                    <span className="text-slate-500">Institution:</span>
                    <span className="font-semibold text-slate-900">{meta.bank_name}</span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-slate-500">Portfolio Number:</span>
                    <span className="font-mono font-semibold text-slate-900">
                      {meta.portfolio_number || "Not printed in statement"}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-slate-500">Valuation Date:</span>
                    <span className="font-semibold text-slate-900">{meta.valuation_date}</span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-slate-500">Report Edited Date:</span>
                    <span className="text-slate-700">{meta.report_edited_date}</span>
                  </p>
                </div>

                <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-1.5">
                  <p className="flex justify-between">
                    <span className="text-slate-500">Total Assets (USD):</span>
                    <span className="font-mono font-bold text-slate-900">
                      ${formatAmount(current.net_assets_summary?.total_assets_usd)}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-slate-500">Securities Market Value:</span>
                    <span className="font-mono text-slate-800">
                      ${formatAmount(current.net_assets_summary?.assets_usd)}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-slate-500">Accrued Interest (Securities):</span>
                    <span className="font-mono text-slate-800">
                      ${formatAmount(current.net_assets_summary?.accrued_interest_securities_usd)}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-slate-500">Net Accrued (Deposits/Loans):</span>
                    <span className="font-mono text-slate-800">
                      ${formatAmount(current.net_assets_summary?.net_accrued_int_deposits_loans_usd)}
                    </span>
                  </p>
                </div>
              </div>
            </div>

            {/* Page 1 Portfolio in USD Performance & Asset Flow Summary */}
            {current.portfolio_summary_performance && (
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">Portfolio Performance & Asset Flow Summary (USD)</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Period: <span className="font-mono font-medium text-slate-700">{current.portfolio_summary_performance.reporting_period || `SINCE 01.01.${meta.valuation_date?.slice(-4) || '2025'}`}</span> | Source: Page {current.portfolio_summary_performance.source_page}
                    </p>
                  </div>
                  <div className="px-3 py-1 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-mono font-bold text-emerald-800">
                    TWR Return: {formatPct(current.portfolio_summary_performance.performance_twr_pct)}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs pt-1">
                  <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-1.5">
                    <span className="font-semibold text-slate-600 uppercase text-[10px] tracking-wider">Asset Baseline</span>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Initial Assets:</span>
                      <span className="font-mono font-semibold text-slate-900">${formatAmount(current.portfolio_summary_performance.initial_assets)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Assets as of {current.portfolio_summary_performance.valuation_date || meta.valuation_date}:</span>
                      <span className="font-mono font-bold text-slate-900">${formatAmount(current.portfolio_summary_performance.ending_assets)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Period Length:</span>
                      <span className="font-mono text-slate-800">{current.portfolio_summary_performance.number_of_days} Days</span>
                    </p>
                  </div>

                  <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-1.5">
                    <span className="font-semibold text-slate-600 uppercase text-[10px] tracking-wider">Securities & Cash Flows</span>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Incoming Securities:</span>
                      <span className="font-mono text-slate-800">${formatAmount(current.portfolio_summary_performance.total_incoming_securities)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Outgoing Securities:</span>
                      <span className="font-mono text-slate-800">${formatAmount(current.portfolio_summary_performance.total_outgoing_securities)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Incoming Cash:</span>
                      <span className="font-mono text-slate-800">${formatAmount(current.portfolio_summary_performance.total_incoming_cash)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Outgoing Cash:</span>
                      <span className="font-mono text-slate-800">${formatAmount(current.portfolio_summary_performance.total_outgoing_cash)}</span>
                    </p>
                  </div>

                  <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 space-y-1.5">
                    <span className="font-semibold text-slate-600 uppercase text-[10px] tracking-wider">Net Variation</span>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Total Net Inc/Out:</span>
                      <span className="font-mono font-semibold text-slate-900">${formatAmount(current.portfolio_summary_performance.total_inc_out_cash_sec)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Change in Total Assets:</span>
                      <span className="font-mono font-bold text-slate-900">${formatAmount(current.portfolio_summary_performance.change_in_total_assets)}</span>
                    </p>
                    <p className="flex justify-between">
                      <span className="text-slate-500">Performance TWR (USD):</span>
                      <span className="font-mono font-bold text-emerald-700">{formatPct(current.portfolio_summary_performance.performance_twr_pct)}</span>
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Portfolio ESG Rating Card */}
            {(meta.portfolio_esg_previous || meta.portfolio_esg_current || meta.portfolio_previous_esg_rating || meta.portfolio_current_esg_rating) && (
              <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-800">Portfolio ESG Rating</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Source Page: <span className="font-mono font-medium text-slate-700">{meta.portfolio_esg_source_page || current.portfolio_summary_performance?.source_page || 1}</span>
                    </p>
                  </div>
                  <div className="px-3 py-1 bg-emerald-50 border border-emerald-200 rounded-lg text-xs font-mono font-bold text-emerald-800">
                    Current: {meta.portfolio_esg_current || meta.portfolio_current_esg_rating || "—"}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
                  <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 flex justify-between items-center">
                    <span className="text-slate-500 font-medium">Previous ESG Rating:</span>
                    <span className="font-mono font-semibold text-slate-900 bg-white px-2.5 py-1 rounded border border-slate-200">
                      {meta.portfolio_esg_previous || meta.portfolio_previous_esg_rating || "—"}
                    </span>
                  </div>
                  <div className="border border-slate-200 rounded-lg p-3 bg-slate-50/50 flex justify-between items-center">
                    <span className="text-slate-500 font-medium">Current ESG Rating:</span>
                    <span className="font-mono font-bold text-emerald-900 bg-emerald-100/70 px-2.5 py-1 rounded border border-emerald-300">
                      {meta.portfolio_esg_current || meta.portfolio_current_esg_rating || "—"}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 2. Asset Allocation */}
        {activeTab === "allocation" && (
          <DataTable
            data={current.asset_allocation}
            columns={[
              { header: "Investment Category", accessorKey: "investment_category" },
              {
                header: "Value in USD",
                accessorKey: "value_usd",
                align: "right",
                cell: (r) => `$${formatAmount(r.value_usd)}`,
              },
              {
                header: "Allocation %",
                accessorKey: "percentage",
                align: "right",
                cell: (r) => formatPct(r.percentage),
              },
              { header: "Raw Value", accessorKey: "raw_value", align: "right" },
              { header: "Source Page", accessorKey: "source_page", align: "center" },
            ]}
          />
        )}

        {/* 3. Currency Breakdown */}
        {activeTab === "currencies" && (
          <DataTable
            data={current.currency_breakdown}
            columns={[
              { header: "Asset Class", accessorKey: "asset_class" },
              {
                header: "Total (000's USD)",
                accessorKey: "total_in_thousands",
                align: "right",
                cell: (r) => formatAmount(r.total_in_thousands),
              },
              {
                header: "Total %",
                accessorKey: "total_percentage",
                align: "right",
                cell: (r) => formatPct(r.total_percentage),
              },
              {
                header: "USD (000's)",
                align: "right",
                cell: (r) => formatAmount(r.currencies?.USD?.amount_in_thousands),
              },
              {
                header: "USD %",
                align: "right",
                cell: (r) => formatPct(r.currencies?.USD?.percentage),
              },
              {
                header: "Source Page",
                accessorKey: "source_page",
                align: "center",
              },
            ]}
          />
        )}

        {/* 4. Holdings */}
        {activeTab === "holdings" && (
          <DataTable
            data={current.holdings}
            columns={[
              { header: "Holding ID", accessorKey: "id", align: "center" },
              { header: "Category", accessorKey: "asset_category" },
              { header: "Security Name", accessorKey: "security_name" },
              {
                header: "ISIN / Secur No",
                accessorKey: "isin_secur_no",
                align: "center",
                cell: (r) => <span className="font-mono text-blue-700 font-medium">{r.isin_secur_no || "—"}</span>,
              },
              {
                header: "Units / Nominal",
                accessorKey: "units_nominal",
                align: "right",
                cell: (r) => {
                  const formatted = formatInteger(r.units_nominal);
                  return formatted !== "—" ? formatted : (r.units_nominal_raw || "—");
                },
              },
              {
                header: "Market Price",
                accessorKey: "market_price",
                align: "right",
                cell: (r) => `${formatAmount(r.market_price)} ${r.market_price_currency || ""}`,
              },
              {
                header: "Price Date",
                accessorKey: "market_price_date",
                align: "center",
              },
              {
                header: "Value in USD",
                accessorKey: "value_in_usd",
                align: "right",
                cell: (r) => <span className="font-semibold">${formatAmount(r.value_in_usd)}</span>,
              },
              {
                header: "Accrued USD",
                accessorKey: "accrued_interest_usd",
                align: "right",
                cell: (r) => (r.accrued_interest_usd ? `$${formatAmount(r.accrued_interest_usd)}` : "—"),
              },
              {
                header: "% Assets",
                accessorKey: "percentage_of_total_assets",
                align: "right",
                cell: (r) => formatPct(r.percentage_of_total_assets),
              },
              { header: "Source Page", accessorKey: "source_page", align: "center" },
            ]}
          />
        )}

        {/* 5. Current Accounts */}
        {activeTab === "accounts" && (
          <DataTable
            data={current.current_accounts}
            columns={[
              { header: "Account ID", accessorKey: "id", align: "center" },
              { header: "Currency", accessorKey: "currency", align: "center" },
              {
                header: "Amount",
                accessorKey: "amount",
                align: "right",
                cell: (r) => formatAmount(r.amount),
              },
              { header: "Account Name", accessorKey: "account_name" },
              { header: "Account Number", accessorKey: "account_number", align: "center" },
              {
                header: "Value in USD",
                accessorKey: "market_value_usd",
                align: "right",
                cell: (r) => `$${formatAmount(r.market_value_usd)}`,
              },
              {
                header: "% Assets",
                accessorKey: "percentage_assets",
                align: "right",
                cell: (r) => formatPct(r.percentage_assets),
              },
              { header: "Source Page", accessorKey: "source_page", align: "center" },
            ]}
          />
        )}

        {/* 6. Loans */}
        {activeTab === "loans" && (
          <div>
            {current.loans && current.loans.length > 0 ? (
              <DataTable
                data={current.loans}
                columns={[
                  { header: "Loan ID", accessorKey: "id", align: "center" },
                  { header: "Currency", accessorKey: "currency", align: "center" },
                  {
                    header: "Original Amount",
                    accessorKey: "amount",
                    align: "right",
                    cell: (r) => formatAmount(r.amount),
                  },
                  { header: "Description", accessorKey: "description" },
                  { header: "Reference", accessorKey: "loan_reference", align: "center" },
                  { header: "Maturity Date", accessorKey: "maturity_date", align: "center" },
                  {
                    header: "Interest Rate %",
                    accessorKey: "interest_rate",
                    align: "right",
                    cell: (r) => (r.interest_rate ? `${r.interest_rate}%` : "—"),
                  },
                  {
                    header: "Accrued Interest",
                    accessorKey: "accrued_interest",
                    align: "right",
                    cell: (r) => formatAmount(r.accrued_interest),
                  },
                  {
                    header: "USD Equivalent",
                    accessorKey: "usd_equivalent",
                    align: "right",
                    cell: (r) => `$${formatAmount(r.usd_equivalent)}`,
                  },
                  {
                    header: "% Assets",
                    accessorKey: "percentage_assets",
                    align: "right",
                    cell: (r) => formatPct(r.percentage_assets),
                  },
                  { header: "Source Page", accessorKey: "source_page", align: "center" },
                ]}
              />
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500 shadow-xs space-y-2">
                <Landmark className="w-8 h-8 text-slate-300 mx-auto mb-1" />
                <div className="inline-flex items-center px-2.5 py-1 rounded bg-slate-100 text-slate-700 text-xs font-mono font-semibold">
                  STATUS: NOT_PRESENT
                </div>
                <p className="text-sm font-medium text-slate-700">No loan or borrowing facilities present in this statement.</p>
                <p className="text-xs text-slate-400">
                  This portfolio statement contains 0 loan or liability positions. No synthetic or zero-amount placeholder records were created.
                </p>
              </div>
            )}
          </div>
        )}

        {/* 7. Transactions */}
        {activeTab === "transactions" && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-600 shadow-xs space-y-3">
            <ArrowLeftRight className="w-8 h-8 text-slate-300 mx-auto" />
            <h4 className="text-sm font-semibold text-slate-800">
              Itemized Transaction Ledger Not Present in Source Statement
            </h4>
            <p className="text-xs text-slate-500 max-w-xl mx-auto leading-relaxed">
              UBP Portfolio Valuation Statements provide position holdings, cash balances, loans, and aggregate performance.
              Individual transaction rows are not itemized in these valuation reports.
              Periodic cash flows are extracted into the <b>Monthly Performance</b> and <b>Annual Performance</b> tables.
            </p>
            <div className="inline-flex items-center px-3 py-1 rounded bg-slate-100 text-slate-600 text-[11px] font-mono">
              Status: NO_ITEMIZED_TRANSACTIONS_IN_VALUATION_STMT
            </div>
          </div>
        )}

        {/* 8. Net Assets Summary */}
        {activeTab === "summary" && (
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
            <h3 className="text-sm font-semibold text-slate-800 mb-3">Summary of Net Assets</h3>
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-100/70 border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4 font-semibold text-slate-700">Summary Field</th>
                  <th className="py-2.5 px-4 font-semibold text-slate-700 text-right">Amount (USD)</th>
                  <th className="py-2.5 px-4 font-semibold text-slate-700 text-right">% of Total</th>
                  <th className="py-2.5 px-4 font-semibold text-slate-700 text-center">Source Page</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                <tr>
                  <td className="py-2.5 px-4 font-sans text-slate-800">Assets</td>
                  <td className="py-2.5 px-4 text-right">${formatAmount(current.net_assets_summary?.assets_usd)}</td>
                  <td className="py-2.5 px-4 text-right">{formatPct(current.net_assets_summary?.assets_pct)}</td>
                  <td className="py-2.5 px-4 text-center">{current.net_assets_summary?.source_page}</td>
                </tr>
                <tr>
                  <td className="py-2.5 px-4 font-sans text-slate-800">Accrued Interest on Securities</td>
                  <td className="py-2.5 px-4 text-right">${formatAmount(current.net_assets_summary?.accrued_interest_securities_usd)}</td>
                  <td className="py-2.5 px-4 text-right">{formatPct(current.net_assets_summary?.accrued_interest_securities_pct)}</td>
                  <td className="py-2.5 px-4 text-center">{current.net_assets_summary?.source_page}</td>
                </tr>
                <tr>
                  <td className="py-2.5 px-4 font-sans text-slate-800">Net Accrued Interest on Deposits & Loans</td>
                  <td className="py-2.5 px-4 text-right">${formatAmount(current.net_assets_summary?.net_accrued_int_deposits_loans_usd)}</td>
                  <td className="py-2.5 px-4 text-right">{formatPct(current.net_assets_summary?.net_accrued_int_deposits_loans_pct)}</td>
                  <td className="py-2.5 px-4 text-center">{current.net_assets_summary?.source_page}</td>
                </tr>
                <tr className="bg-slate-50 font-bold">
                  <td className="py-2.5 px-4 font-sans text-slate-900">Total Assets</td>
                  <td className="py-2.5 px-4 text-right text-slate-900">${formatAmount(current.net_assets_summary?.total_assets_usd)}</td>
                  <td className="py-2.5 px-4 text-right text-slate-900">{formatPct(current.net_assets_summary?.total_assets_pct)}</td>
                  <td className="py-2.5 px-4 text-center">{current.net_assets_summary?.source_page}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* 9. Exchange Rates */}
        {activeTab === "rates" && (
          <DataTable
            data={current.exchange_rates}
            columns={[
              { header: "Base Currency", accessorKey: "base_currency", align: "center" },
              { header: "Target Currency", accessorKey: "target_currency", align: "center" },
              {
                header: "Exchange Rate",
                accessorKey: "rate",
                align: "right",
                cell: (r) => formatRate(r.rate),
              },
              { header: "Source Text", accessorKey: "raw_text" },
              { header: "Source Page", accessorKey: "source_page", align: "center" },
            ]}
          />
        )}

        {/* 10. Monthly Performance */}
        {activeTab === "monthly" && (
          <DataTable
            data={current.monthly_performance}
            columns={[
              {
                header: "Period",
                accessorKey: "period",
                align: "center",
                cell: (r) => <span className={r.is_total_row ? "font-bold text-slate-900" : ""}>{r.period}</span>,
              },
              {
                header: "Performance %",
                accessorKey: "performance_pct",
                align: "right",
                cell: (r) => formatPct(r.performance_pct),
              },
              {
                header: "Cumulative %",
                accessorKey: "cumulative_performance_pct",
                align: "right",
                cell: (r) => formatPct(r.cumulative_performance_pct),
              },
              {
                header: "End of Period Assets",
                accessorKey: "end_of_period_assets",
                align: "right",
                cell: (r) => (r.end_of_period_assets !== undefined && r.end_of_period_assets !== null ? `$${formatAmount(r.end_of_period_assets)}` : "—"),
              },
              {
                header: "Deposits & Withdrawals",
                accessorKey: "period_deposits_withdrawals",
                align: "right",
                cell: (r) => (r.period_deposits_withdrawals !== undefined && r.period_deposits_withdrawals !== null ? `$${formatAmount(r.period_deposits_withdrawals)}` : "—"),
              },
              {
                header: "Change in Total Assets",
                accessorKey: "change_in_total_assets",
                align: "right",
                cell: (r) => (r.change_in_total_assets !== undefined && r.change_in_total_assets !== null ? `$${formatAmount(r.change_in_total_assets)}` : "—"),
              },
              {
                header: "Net Income",
                accessorKey: "net_income",
                align: "right",
                cell: (r) => (r.net_income !== undefined && r.net_income !== null ? `$${formatAmount(r.net_income)}` : "—"),
              },
              {
                header: "Return on Net Income %",
                accessorKey: "return_on_net_income_pct",
                align: "right",
                cell: (r) => formatPct(r.return_on_net_income_pct),
              },
              {
                header: "Row Type",
                accessorKey: "row_type",
                align: "center",
                cell: (r) => {
                  const type = r.is_initial_row ? "INITIAL" : (r.is_total_row ? "TOTAL" : "MONTHLY");
                  const color = type === "INITIAL" ? "bg-amber-100 text-amber-800" : (type === "TOTAL" ? "bg-slate-200 text-slate-800 font-bold" : "bg-slate-100 text-slate-700");
                  return <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${color}`}>{type}</span>;
                }
              },
              { header: "Source Page", accessorKey: "source_page", align: "center" },
            ]}
          />
        )}

        {/* 11. Annual Performance */}
        {activeTab === "annual" && (
          <DataTable
            data={current.annual_performance}
            columns={[
              {
                header: "Period",
                accessorKey: "period",
                align: "center",
                cell: (r) => <span className={r.is_total_row ? "font-bold text-slate-900" : ""}>{r.period}</span>,
              },
              {
                header: "Performance %",
                accessorKey: "performance_pct",
                align: "right",
                cell: (r) => formatPct(r.performance_pct),
              },
              {
                header: "Cumulative %",
                accessorKey: "cumulative_performance_pct",
                align: "right",
                cell: (r) => formatPct(r.cumulative_performance_pct),
              },
              {
                header: "End of Period Assets",
                accessorKey: "end_of_period_assets",
                align: "right",
                cell: (r) => (r.end_of_period_assets !== undefined && r.end_of_period_assets !== null ? `$${formatAmount(r.end_of_period_assets)}` : "—"),
              },
              {
                header: "Deposits & Withdrawals",
                accessorKey: "period_deposits_withdrawals",
                align: "right",
                cell: (r) => (r.period_deposits_withdrawals !== undefined && r.period_deposits_withdrawals !== null ? `$${formatAmount(r.period_deposits_withdrawals)}` : "—"),
              },
              {
                header: "Change in Total Assets",
                accessorKey: "change_in_total_assets",
                align: "right",
                cell: (r) => (r.change_in_total_assets !== undefined && r.change_in_total_assets !== null ? `$${formatAmount(r.change_in_total_assets)}` : "—"),
              },
              {
                header: "Net Income",
                accessorKey: "net_income",
                align: "right",
                cell: (r) => (r.net_income !== undefined && r.net_income !== null ? `$${formatAmount(r.net_income)}` : "—"),
              },
              {
                header: "Return on Net Income %",
                accessorKey: "return_on_net_income_pct",
                align: "right",
                cell: (r) => formatPct(r.return_on_net_income_pct),
              },
              {
                header: "Row Type",
                accessorKey: "row_type",
                align: "center",
                cell: (r) => {
                  const type = r.is_initial_row ? "INITIAL" : (r.is_total_row ? "TOTAL" : (/\d{2}\.\d{2}\.\d{4}/.test(r.period) ? "PERIODIC" : "ANNUAL"));
                  const color = type === "INITIAL" ? "bg-amber-100 text-amber-800" : (type === "TOTAL" ? "bg-slate-200 text-slate-800 font-bold" : (type === "PERIODIC" ? "bg-blue-100 text-blue-800 font-semibold" : "bg-slate-100 text-slate-700"));
                  return <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${color}`}>{type}</span>;
                }
              },
              { header: "Source Page", accessorKey: "source_page", align: "center" },
            ]}
          />
        )}

        {/* 12. Comments & Disclosures */}
        {activeTab === "comments" && (
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
            <div>
              <h4 className="text-xs font-semibold text-slate-800 uppercase tracking-wider mb-1">
                General Information Disclaimer
              </h4>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-700 leading-relaxed whitespace-pre-line font-mono">
                {current.comments_disclosures?.general_information || "Not present in statement."}
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-slate-800 uppercase tracking-wider mb-1">
                Product Risk Classification (PRC)
              </h4>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-700 leading-relaxed whitespace-pre-line font-mono">
                {current.comments_disclosures?.product_risk_classification || "Not present in statement."}
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-slate-800 uppercase tracking-wider mb-1">
                Acknowledgement of Assets
              </h4>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-700 leading-relaxed whitespace-pre-line font-mono">
                {current.comments_disclosures?.acknowledgement_of_assets || "Not present in statement."}
              </div>
            </div>
          </div>
        )}

        {/* 13. Validation Report */}
        {activeTab === "validation" && (
          <DataTable
            data={current.validation_checks}
            columns={[
              {
                header: "Status",
                accessorKey: "level",
                align: "center",
                cell: (r) => (
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                      r.level === "PASS"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : r.level === "WARNING"
                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                        : "bg-red-50 text-red-700 border border-red-200"
                    }`}
                  >
                    {r.level}
                  </span>
                ),
              },
              { header: "Category", accessorKey: "category" },
              { header: "Rule Check", accessorKey: "name" },
              { header: "Verdict / Message", accessorKey: "message" },
            ]}
          />
        )}
      </div>
    </div>
  );
};
