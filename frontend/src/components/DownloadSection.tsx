import React from "react";
import { Download, FileSpreadsheet, Archive, CheckCircle2, AlertTriangle } from "lucide-react";
import { StatementExtractionResult } from "../services/api";

interface DownloadSectionProps {
  jobId: string;
  results: StatementExtractionResult[];
}

export const DownloadSection: React.FC<DownloadSectionProps> = ({ jobId, results }) => {
  if (results.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs my-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-emerald-700" />
            Generated Financial Workbooks & Downloads
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            16-worksheet structured Excel workbooks conforming to Taurus extraction standards.
          </p>
        </div>

        <a
          href={`/api/jobs/${jobId}/download-all`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold shadow-xs transition"
        >
          <Archive className="w-4 h-4" />
          Download All Excel Workbooks (.ZIP)
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {results.map((res, idx) => {
          const meta = res.metadata;
          const fails = res.validation_checks.filter((c) => c.level === "FAIL").length;
          const warnings = res.validation_checks.filter((c) => c.level === "WARNING").length;

          return (
            <div
              key={idx}
              className="border border-slate-200 rounded-lg p-3.5 bg-slate-50/50 flex flex-col justify-between hover:border-slate-300 transition"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="truncate">
                    <p className="text-xs font-semibold text-slate-800 truncate" title={meta.filename}>
                      {meta.filename}
                    </p>
                    <p className="text-[11px] text-slate-500 font-mono">
                      Portfolio: {meta.portfolio_number || "Unknown"} | P.{meta.total_pages}
                    </p>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0 ${
                      fails > 0
                        ? "bg-red-50 text-red-700 border border-red-200"
                        : warnings > 0
                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                        : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    }`}
                  >
                    {fails === 0 && warnings === 0 && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                    {fails === 0 && warnings > 0 && <AlertTriangle className="w-3 h-3 text-amber-600" />}
                    {fails > 0 ? "FAIL" : warnings > 0 ? "WARNING" : "PASS"}
                  </span>
                </div>

                <div className="text-[11px] text-slate-500 space-y-0.5 mb-3 font-mono">
                  <p>Holdings: {res.holdings?.length || 0} rows</p>
                  <p>Cash Accounts: {res.current_accounts?.length || 0} rows</p>
                  <p>Loans: {res.loans?.length || 0} rows</p>
                  <p>Valuation Date: {meta.valuation_date}</p>
                </div>
              </div>

              <a
                href={`/api/jobs/${jobId}/download/${idx}`}
                className="inline-flex items-center justify-center gap-1.5 w-full py-1.5 px-3 bg-white hover:bg-slate-100 border border-slate-300 rounded text-xs font-medium text-slate-700 transition shadow-2xs"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" />
                Download Excel (.xlsx)
              </a>
            </div>
          );
        })}
      </div>
    </div>
  );
};
