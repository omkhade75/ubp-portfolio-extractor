import React, { useState, useEffect } from "react";
import {
  FileText,
  Shield,
  Cpu,
  Lock,
  Layers,
  Sparkles,
  AlertCircle,
  RotateCcw
} from "lucide-react";
import { UploadZone } from "../components/UploadZone";
import { ProcessingProgress } from "../components/ProcessingProgress";
import { ValidationCards } from "../components/ValidationCards";
import { ExtractedDataTabs } from "../components/ExtractedDataTabs";
import { DownloadSection } from "../components/DownloadSection";
import {
  uploadStatements,
  getJobStatus,
  StatementExtractionResult,
  ExtractionJobStatus,
  JobNotFoundError
} from "../services/api";

export const Home: React.FC = () => {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<ExtractionJobStatus | null>(null);
  const [activeResultIndex, setActiveResultIndex] = useState<number>(0);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Poll job status while processing with bounded retries and 404 safety
  useEffect(() => {
    if (!currentJobId) return;
    if (jobStatus?.status === "COMPLETED" || jobStatus?.status === "FAILED") return;

    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 5;

    const interval = setInterval(async () => {
      try {
        const status = await getJobStatus(currentJobId);
        consecutiveErrors = 0;
        setJobStatus(status);

        if (status.status === "FAILED") {
          setErrorMessage(status.error_message || "Extraction failed");
          clearInterval(interval);
        }
      } catch (err: any) {
        if (err instanceof JobNotFoundError || err.name === "JobNotFoundError") {
          clearInterval(interval);
          setIsUploading(false);
          setJobStatus(null);
          setCurrentJobId(null);
          setErrorMessage(
            "The extraction session was not found or the server container restarted. Please click below to re-upload your document."
          );
          return;
        }

        consecutiveErrors++;
        console.warn(`Polling attempt error (${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}):`, err.message);
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          clearInterval(interval);
          setIsUploading(false);
          setErrorMessage(
            "Connection to the extraction server was interrupted. Please check your network or re-upload your document."
          );
        }
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [currentJobId, jobStatus?.status]);

  const handleFilesSelected = async (files: File[]) => {
    if (!files || files.length === 0) return;
    try {
      setIsUploading(true);
      setErrorMessage(null);
      setJobStatus(null);
      const res = await uploadStatements(files);
      setCurrentJobId(res.job_id);
    } catch (err: any) {
      setErrorMessage(err.message || "Upload and extraction failed.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setCurrentJobId(null);
    setJobStatus(null);
    setErrorMessage(null);
    setActiveResultIndex(0);
  };

  const isProcessing =
    isUploading ||
    (!!jobStatus && !["COMPLETED", "FAILED", "CANCELLED"].includes(jobStatus.status));
  const results = jobStatus?.results || [];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-30 shadow-2xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white font-bold text-sm">
                UBP
              </div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">
                UBP Portfolio Extractor
              </h1>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Automated Portfolio Statement Extraction & Validation
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {(results.length > 0 || errorMessage) && (
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset / New Upload
              </button>
            )}
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
              <Shield className="w-3.5 h-3.5 text-emerald-600" />
              Isolated Server-Side Processing
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
              <Cpu className="w-3.5 h-3.5 text-blue-600" />
              Python Financial Extraction Engine
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-300">
              <Lock className="w-3.5 h-3.5 text-slate-500" />
              Deterministic Processing / No External AI Calls
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        {/* Error notification */}
        {errorMessage && (
          <div className="mb-4 p-3.5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Upload Zone */}
        <UploadZone
          onFilesSelected={handleFilesSelected}
          disabled={isProcessing}
        />

        {/* Live Processing Pipeline */}
        {isProcessing && jobStatus && (
          <ProcessingProgress
            phase={jobStatus.phase}
            stage={jobStatus.stage}
            progressPercentage={jobStatus.progress_percentage}
            currentFile={jobStatus.current_file}
            totalFiles={jobStatus.total_files}
            processedFiles={jobStatus.processed_files}
          />
        )}

        {/* Validation Cards & Summary Dashboard */}
        {jobStatus?.status === "COMPLETED" && results.length > 0 && (
          <>
            <ValidationCards
              results={results}
              activeResultIndex={activeResultIndex}
            />

            {/* Extracted Data Tabs */}
            <ExtractedDataTabs
              results={results}
              activeResultIndex={activeResultIndex}
              onSelectResultIndex={setActiveResultIndex}
            />

            {/* Download Section */}
            <DownloadSection
              jobId={currentJobId || ""}
              results={results}
            />
          </>
        )}
      </main>
    </div>
  );
};
