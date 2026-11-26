import React, { useId, useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

interface UploadZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  onFilesSelected,
  disabled = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const fileInputId = useId();

  const triggerFilePicker = () => {
    if (disabled) return;
    const input = fileInputRef.current;
    if (!input) return;
    // Clear previous selection so re-selecting the same file always triggers onChange
    input.value = "";
    input.click();
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (disabled) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const validFiles: File[] = [];
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        const file = e.dataTransfer.files[i];
        if (file.name.toLowerCase().endsWith(".pdf") || file.name.toLowerCase().endsWith(".zip")) {
          validFiles.push(file);
        }
      }
      if (validFiles.length > 0) {
        onFilesSelected(validFiles);
      }
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      onFilesSelected(filesArray);
      e.target.value = "";
    }
  };

  const handleZoneClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled) return;
    if (e.target === fileInputRef.current) return;
    triggerFilePicker();
  };

  const handleBrowseClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    triggerFilePicker();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      triggerFilePicker();
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs relative">
      {/* Native file input lives as a sibling outside the clickable dropzone to prevent bubbled double-click activation errors */}
      <input
        id={fileInputId}
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.zip,application/pdf,application/zip"
        onChange={handleFileInputChange}
        onClick={(e) => e.stopPropagation()}
        className="sr-only"
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0, 0, 0, 0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
        disabled={disabled}
        aria-label="Upload UBP Portfolio PDF statements or ZIP archive"
      />

      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-controls={fileInputId}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleZoneClick}
        onKeyDown={handleKeyDown}
        className={`relative border-2 border-dashed rounded-lg p-8 flex flex-col items-center justify-center cursor-pointer transition-all focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 ${
          isDragging
            ? "border-slate-800 bg-slate-50"
            : "border-slate-300 hover:border-slate-400 hover:bg-slate-50/50"
        } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-700 mb-3">
          <UploadCloud className="w-6 h-6" />
        </div>

        <p className="text-sm font-semibold text-slate-800 mb-1">
          Drop UBP Portfolio PDF statements or ZIP here, or{" "}
          <button
            type="button"
            disabled={disabled}
            onClick={handleBrowseClick}
            aria-controls={fileInputId}
            className="text-blue-600 underline hover:text-blue-700 font-semibold cursor-pointer disabled:cursor-not-allowed focus:outline-none focus:ring-1 focus:ring-blue-500 rounded-xs"
          >
            browse
          </button>
        </p>
        <p className="text-xs text-slate-500">
          Supports individual PDFs, multiple files, or zipped bundles. Deterministic server-side extraction.
        </p>
      </div>
    </div>
  );
};
