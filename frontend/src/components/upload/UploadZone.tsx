"use client";
import { useState, useRef, useCallback } from "react";
import { Upload, FileSpreadsheet, FileText, AlertCircle, CheckCircle } from "lucide-react";
import { uploadFile, getUpload } from "@/lib/api";
import clsx from "clsx";

interface UploadResult {
  id: number;
  original_filename: string;
  row_count: number;
  mapped_count: number;
  unmapped_count: number;
  status: string;
  error_message?: string;
}

interface Props {
  onUploadComplete?: (result: UploadResult) => void;
}

const FileIcon = ({ type }: { type: string }) => {
  if (["xls", "xlsx"].includes(type)) return <FileSpreadsheet size={40} className="text-green-500" />;
  if (type === "pdf") return <FileText size={40} className="text-red-500" />;
  return <FileText size={40} className="text-blue-500" />;
};

export default function UploadZone({ onUploadComplete }: Props) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<"idle" | "uploading" | "processing" | "done" | "error">("idle");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<NodeJS.Timeout>();

  const pollStatus = useCallback((uploadId: number) => {
    setPhase("processing");
    let attempts = 0;
    const poll = async () => {
      attempts++;
      if (attempts > 240) {
        setPhase("error");
        setError("Processing timed out (8 min). The file may be too large or the AI service is slow. Please try again.");
        return;
      }
      try {
        const { data } = await getUpload(uploadId);
        if (data.status === "completed") {
          setResult(data);
          setPhase("done");
          onUploadComplete?.(data);
        } else if (data.status === "failed") {
          setPhase("error");
          setError(data.error_message || "Processing failed");
        } else {
          pollRef.current = setTimeout(poll, 2000);
        }
      } catch {
        pollRef.current = setTimeout(poll, 2000);
      }
    };
    poll();
  }, [onUploadComplete]);

  const handleFile = useCallback(async (f: File) => {
    const ext = f.name.split(".").pop()?.toLowerCase() || "";
    if (!["pdf", "xls", "xlsx", "csv"].includes(ext)) {
      setError("Unsupported file type. Please upload PDF, XLS, XLSX, or CSV.");
      return;
    }
    setFile(f);
    setPhase("uploading");
    setProgress(0);
    setError("");
    setResult(null);

    try {
      const { data } = await uploadFile(f, setProgress);
      setProgress(100);
      pollStatus(data.id);
    } catch (e: any) {
      setPhase("error");
      setError(e.response?.data?.detail || "Upload failed. Please try again.");
    }
  }, [pollStatus]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const reset = () => {
    setFile(null);
    setPhase("idle");
    setProgress(0);
    setError("");
    setResult(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="space-y-4">
      {phase === "idle" && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={clsx(
            "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all",
            dragging
              ? "border-indigo-500 bg-indigo-50"
              : "border-gray-300 hover:border-indigo-400 hover:bg-gray-50"
          )}
        >
          <Upload className="mx-auto mb-4 text-gray-400" size={40} />
          <p className="text-lg font-semibold text-gray-700">
            Drop your bank statement here
          </p>
          <p className="text-sm text-gray-500 mt-1">
            or click to browse files
          </p>
          <div className="flex justify-center gap-3 mt-4">
            {["PDF", "XLS", "XLSX", "CSV"].map((t) => (
              <span
                key={t}
                className="px-3 py-1 bg-white border border-gray-200 rounded-full text-xs font-medium text-gray-500"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.xls,.xlsx,.csv"
        onChange={onInputChange}
      />

      {(phase === "uploading" || phase === "processing") && file && (
        <div className="border border-gray-200 rounded-xl p-6 bg-white">
          <div className="flex items-center gap-4 mb-4">
            <FileIcon type={file.name.split(".").pop() || ""} />
            <div className="flex-1">
              <p className="font-medium text-gray-800">{file.name}</p>
              <p className="text-sm text-gray-500">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-600">
              <span>
                {phase === "uploading"
                  ? "Uploading..."
                  : "Parsing & classifying transactions..."}
              </span>
              {phase === "uploading" && <span>{progress}%</span>}
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                style={{
                  width: phase === "processing" ? "100%" : `${progress}%`,
                  animation: phase === "processing" ? "pulse 1.5s ease-in-out infinite" : undefined,
                }}
              />
            </div>
            {phase === "processing" && (
              <p className="text-xs text-gray-400">
                AI is classifying each transaction. Large files may take 2–5 minutes…
              </p>
            )}
          </div>
        </div>
      )}

      {phase === "done" && result && (
        <div className="border border-green-200 rounded-xl p-6 bg-green-50">
          <div className="flex items-start gap-3">
            <CheckCircle className="text-green-600 flex-shrink-0 mt-0.5" size={22} />
            <div className="flex-1">
              <p className="font-semibold text-green-800">Upload Successful!</p>
              <p className="text-sm text-green-700 mt-1">{result.original_filename}</p>
              <div className="flex gap-4 mt-3 text-sm">
                <div className="text-center">
                  <p className="font-bold text-gray-800">{result.row_count}</p>
                  <p className="text-gray-500 text-xs">Total Rows</p>
                </div>
                <div className="text-center">
                  <p className="font-bold text-green-700">{result.mapped_count}</p>
                  <p className="text-gray-500 text-xs">Mapped</p>
                </div>
                <div className="text-center">
                  <p className="font-bold text-amber-700">{result.unmapped_count}</p>
                  <p className="text-gray-500 text-xs">Unmapped</p>
                </div>
              </div>
            </div>
          </div>
          <button
            onClick={reset}
            className="mt-4 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Upload another file →
          </button>
        </div>
      )}

      {phase === "error" && (
        <div className="border border-red-200 rounded-xl p-6 bg-red-50">
          <div className="flex items-start gap-3">
            <AlertCircle className="text-red-600 flex-shrink-0 mt-0.5" size={22} />
            <div>
              <p className="font-semibold text-red-800">Upload Failed</p>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
          <button
            onClick={reset}
            className="mt-4 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Try again →
          </button>
        </div>
      )}
    </div>
  );
}
