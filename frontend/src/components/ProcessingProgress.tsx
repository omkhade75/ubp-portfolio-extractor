import React from "react";
import { CheckCircle2, Loader2, Clock } from "lucide-react";

interface ProcessingProgressProps {
  phase: string;
  progressPercentage: number;
  currentFile?: string;
  totalFiles: number;
  processedFiles: number;
}

const PHASES = [
  "File validation",
  "PDF inspection",
  "Statement/template identification",
  "Page classification",
  "Text and table extraction",
  "Data normalization",
  "Financial validation",
  "Excel generation",
];

export const ProcessingProgress: React.FC<ProcessingProgressProps> = ({
  phase,
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

      {/* 8-phase pipeline grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-100">
        {PHASES.map((pName, idx) => {
          const isDone = progressPercentage === 100 || (processedFiles > 0 && idx < 6);
          const isCurrent = phase.toLowerCase().includes(pName.toLowerCase());

          return (
            <div
              key={idx}
              className={`flex items-center gap-1.5 p-2 rounded text-xs transition ${
                isCurrent
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
              <span className="truncate">{pName}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
