import React from "react";
import { CheckCircle2, Loader2, Clock } from "lucide-react";

interface ProcessingProgressProps {
  phase: string;
  stage?: string;
  progressPercentage: number;
  currentFile?: string;
  totalFiles: number;
  processedFiles: number;
}

const STAGES = [
  { key: "QUEUED", label: "File validation", minPct: 0 },
  { key: "INSPECTING", label: "PDF inspection", minPct: 5 },
  { key: "CLASSIFYING", label: "Page classification", minPct: 20 },
  { key: "EXTRACTING", label: "Text & table extraction", minPct: 40 },
  { key: "NORMALIZING", label: "Data normalization", minPct: 65 },
  { key: "VALIDATING", label: "Financial validation", minPct: 80 },
  { key: "GENERATING_EXCEL", label: "Excel generation", minPct: 90 },
  { key: "COMPLETED", label: "Completed", minPct: 100 },
];

export const ProcessingProgress: React.FC<ProcessingProgressProps> = ({
  phase,
  stage,
  progressPercentage,
  currentFile,
  totalFiles,
  processedFiles,
}) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs my-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
            <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
            Active Extraction Pipeline
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {currentFile ? `Current Statement: ${currentFile}` : "Preparing extraction engine..."}
          </p>
        </div>
        <div className="text-right">
          <span className="text-lg font-bold font-mono text-slate-900">{progressPercentage}%</span>
          <p className="text-[11px] text-slate-500">
            {processedFiles} of {totalFiles} files complete
          </p>
        </div>
      </div>

      {/* Main Progress Bar */}
      <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden mb-4">
        <div
          className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
          style={{ width: `${progressPercentage}%` }}
        />
      </div>

      {/* 8-stage pipeline grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-100">
        {STAGES.map((s, idx) => {
          const isDone = progressPercentage >= (idx === STAGES.length - 1 ? 100 : STAGES[idx + 1].minPct);
          const isCurrent =
            (stage && stage.toUpperCase() === s.key) ||
            (!stage && phase.toLowerCase().includes(s.label.toLowerCase())) ||
            (!isDone && progressPercentage >= s.minPct);

          return (
            <div
              key={idx}
              className={`flex items-center gap-1.5 p-2 rounded text-xs transition ${
                isCurrent && !isDone
                  ? "bg-blue-50 text-blue-800 font-semibold border border-blue-200"
                  : isDone
                  ? "text-slate-600 bg-slate-50"
                  : "text-slate-400 bg-slate-50/50"
              }`}
            >
              {isDone ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin shrink-0" />
              ) : (
                <Clock className="w-3.5 h-3.5 text-slate-300 shrink-0" />
              )}
              <span className="truncate">{s.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
