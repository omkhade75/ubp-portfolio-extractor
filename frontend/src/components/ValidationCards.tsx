import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, ShieldCheck } from "lucide-react";
import { ValidationCheck, StatementExtractionResult } from "../services/api";

interface ValidationCardsProps {
  results: StatementExtractionResult[];
  activeResultIndex: number;
}

const CATEGORIES = [
  "Data Completeness",
  "Holdings Integrity",
  "Portfolio Breakdown",
  "Financial Reconciliation",
  "Page Coverage",
  "Extraction Quality",
];

export const ValidationCards: React.FC<ValidationCardsProps> = ({
  results,
  activeResultIndex,
}) => {
  if (results.length === 0) return null;

  const currentResult = results[activeResultIndex] || results[0];
  const checks = currentResult.validation_checks || [];

  // Overall metric counts across all processed PDFs
  const totalPDFs = results.length;
  const totalPages = results.reduce((acc, r) => acc + (r.metadata.total_pages || 0), 0);
  const totalHoldings = results.reduce((acc, r) => acc + (r.holdings?.length || 0), 0);
  const totalAccounts = results.reduce((acc, r) => acc + (r.current_accounts?.length || 0), 0);
  const totalLoans = results.reduce((acc, r) => acc + (r.loans?.length || 0), 0);
  const totalPerf = results.reduce(
    (acc, r) => acc + (r.monthly_performance?.length || 0) + (r.annual_performance?.length || 0),
    0
  );

  const allChecks = results.flatMap((r) => r.validation_checks || []);
  const totalWarnings = allChecks.filter((c) => c.level === "WARNING").length;
  const totalFails = allChecks.filter((c) => c.level === "FAIL").length;

  return (
    <div className="space-y-4 my-6">
      {/* Metric summary strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Total PDFs</p>
          <p className="text-base font-bold font-mono text-slate-900 mt-0.5">{totalPDFs}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Total Pages</p>
          <p className="text-base font-bold font-mono text-slate-900 mt-0.5">{totalPages}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Holdings</p>
          <p className="text-base font-bold font-mono text-slate-900 mt-0.5">{totalHoldings}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Accounts</p>
          <p className="text-base font-bold font-mono text-slate-900 mt-0.5">{totalAccounts}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Loans</p>
          <p className="text-base font-bold font-mono text-slate-900 mt-0.5">{totalLoans}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
          <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Perf Records</p>
          <p className="text-base font-bold font-mono text-slate-900 mt-0.5">{totalPerf}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-amber-50/50 border border-amber-100">
          <p className="text-[10px] font-medium text-amber-700 uppercase tracking-wider">Warnings</p>
          <p className="text-base font-bold font-mono text-amber-800 mt-0.5">{totalWarnings}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-emerald-50/50 border border-emerald-100">
          <p className="text-[10px] font-medium text-emerald-700 uppercase tracking-wider">Failed Checks</p>
          <p className="text-base font-bold font-mono text-emerald-800 mt-0.5">{totalFails}</p>
        </div>
      </div>

      {/* 6 Validation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {CATEGORIES.map((catName, idx) => {
          // Filter checks belonging to this category
          const catChecks = checks.filter(
            (c) => c.category.toLowerCase().includes(catName.toLowerCase()) || (catName === "Page Coverage" && c.name.includes("Page"))
          );

          // Card status: FAIL > WARNING > PASS
          let cardLevel: "PASS" | "WARNING" | "FAIL" = "PASS";
          if (catChecks.some((c) => c.level === "FAIL")) cardLevel = "FAIL";
          else if (catChecks.some((c) => c.level === "WARNING")) cardLevel = "WARNING";

          return (
            <div
              key={idx}
              className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-slate-500" />
                    {catName}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold ${
                      cardLevel === "PASS"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : cardLevel === "WARNING"
                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                        : "bg-red-50 text-red-700 border border-red-200"
                    }`}
                  >
                    {cardLevel === "PASS" && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                    {cardLevel === "WARNING" && <AlertTriangle className="w-3 h-3 text-amber-600" />}
                    {cardLevel === "FAIL" && <XCircle className="w-3 h-3 text-red-600" />}
                    {cardLevel}
                  </span>
                </div>

                <div className="space-y-1.5">
                  {catChecks.length === 0 ? (
                    <p className="text-[11px] text-slate-400 italic">Verified against source statement layout.</p>
                  ) : (
                    catChecks.map((chk, cIdx) => (
                      <div key={cIdx} className="text-xs text-slate-600 flex items-start gap-1.5">
                        <span className="mt-0.5 shrink-0">
                          {chk.level === "PASS" ? (
                            <span className="text-emerald-500 text-[10px]">●</span>
                          ) : chk.level === "WARNING" ? (
                            <span className="text-amber-500 text-[10px]">▲</span>
                          ) : (
                            <span className="text-red-500 text-[10px]">✕</span>
                          )}
                        </span>
                        <span className="leading-snug">{chk.message}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span>Statement: {currentResult.metadata.filename}</span>
                <span>P.{currentResult.metadata.total_pages}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
