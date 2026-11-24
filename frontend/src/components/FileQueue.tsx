import React from "react";
import { Trash2, FileText, Play, RefreshCw } from "lucide-react";

interface QueuedFile {
  file?: File;
  name: string;
  size: number;
  portfolioNumber?: string;
  valuationDate?: string;
  pageCount?: number;
  pdfType: "Text" | "OCR";
  status: "Queued" | "Ready" | "Processing" | "Completed" | "Failed";
}

interface FileQueueProps {
  files: QueuedFile[];
  onRemoveFile: (index: number) => void;
  onClearAll: () => void;
  onStartExtraction: () => void;
  isProcessing: boolean;
}

export const FileQueue: React.FC<FileQueueProps> = ({
  files,
  onRemoveFile,
  onClearAll,
  onStartExtraction,
  isProcessing,
}) => {
  if (files.length === 0) return null;

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs mt-4">
      <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-700" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
            Selected Statements ({files.length})
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClearAll}
            disabled={isProcessing}
            className="text-xs text-slate-600 hover:text-slate-900 font-medium px-2.5 py-1 rounded border border-slate-300 hover:bg-slate-100 transition disabled:opacity-50"
          >
            Clear All
          </button>
          <button
            type="button"
            onClick={onStartExtraction}
            disabled={isProcessing}
            className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded shadow-xs transition disabled:opacity-50"
          >
            {isProcessing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Extracting...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                Start Extraction
              </>
            )}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-700">
          <thead className="bg-slate-100/70 text-slate-600 font-medium border-b border-slate-200">
            <tr>
              <th className="py-2.5 px-4">Filename</th>
              <th className="py-2.5 px-4">File Size</th>
              <th className="py-2.5 px-4">Portfolio Number</th>
              <th className="py-2.5 px-4">Valuation Date</th>
              <th className="py-2.5 px-4">Pages</th>
              <th className="py-2.5 px-4">PDF Type</th>
              <th className="py-2.5 px-4">Status</th>
              <th className="py-2.5 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {files.map((f, idx) => (
              <tr key={idx} className="hover:bg-slate-50/50">
                <td className="py-2.5 px-4 font-medium text-slate-900 flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate max-w-xs">{f.name}</span>
                </td>
                <td className="py-2.5 px-4 text-slate-500">{formatBytes(f.size)}</td>
                <td className="py-2.5 px-4 font-mono text-slate-600">
                  {f.portfolioNumber || "Pending"}
                </td>
                <td className="py-2.5 px-4 text-slate-600">
                  {f.valuationDate || "Pending"}
                </td>
                <td className="py-2.5 px-4 text-slate-600">
                  {f.pageCount || "Auto-detect"}
                </td>
                <td className="py-2.5 px-4">
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200">
                    {f.pdfType}
                  </span>
                </td>
                <td className="py-2.5 px-4">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                      f.status === "Completed"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : f.status === "Processing"
                        ? "bg-amber-50 text-amber-700 border border-amber-200 animate-pulse"
                        : f.status === "Failed"
                        ? "bg-red-50 text-red-700 border border-red-200"
                        : "bg-slate-100 text-slate-600 border border-slate-200"
                    }`}
                  >
                    {f.status}
                  </span>
                </td>
                <td className="py-2.5 px-4 text-right">
                  <button
                    type="button"
                    onClick={() => onRemoveFile(idx)}
                    disabled={isProcessing}
                    className="text-slate-400 hover:text-red-600 transition disabled:opacity-40 p-1"
                    title="Remove file"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
