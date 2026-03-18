"use client";
import { useState, useEffect, useRef } from "react";
import UploadZone from "@/components/upload/UploadZone";
import { getUploads, getMyBusinessAccounts, deleteUpload, Upload } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  FileText,
  FileSpreadsheet,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader,
  Trash2,
  RefreshCw,
  Building2,
} from "lucide-react";
import clsx from "clsx";

const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case "completed":
      return <CheckCircle size={16} className="text-green-500" />;
    case "failed":
      return <AlertCircle size={16} className="text-red-500" />;
    case "processing":
      return <Loader size={16} className="text-indigo-500 animate-spin" />;
    default:
      return <Clock size={16} className="text-gray-400" />;
  }
};

const FileTypeIcon = ({ type }: { type: string }) => {
  if (["xls", "xlsx"].includes(type))
    return <FileSpreadsheet size={20} className="text-green-500" />;
  return <FileText size={20} className="text-red-500" />;
};

export default function UploadPage() {
  const { activeBusinessId } = useAuth();

  const [uploads, setUploads] = useState<Upload[]>([]);
  const [businessName, setBusinessName] = useState<string>("");
  const [loadingUploads, setLoadingUploads] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const uploadsRef = useRef<Upload[]>([]);

  const fetchUploads = async () => {
    try {
      const { data } = await getUploads();
      setUploads(data);
      uploadsRef.current = data;
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingUploads(false);
    }
  };

  // ── Re-fetch uploads and resolve business name when active business changes ─
  useEffect(() => {
    setUploads([]);
    setLoadingUploads(true);

    fetchUploads();

    // Resolve business name for the "Uploading to" indicator
    getMyBusinessAccounts()
      .then(({ data }) => {
        const ba = data.find((b) => b.id === activeBusinessId);
        setBusinessName(ba?.name ?? "");
      })
      .catch(() => setBusinessName(""));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBusinessId]);

  // Poll every 3s only while uploads are pending/processing (ref avoids re-registering interval)
  useEffect(() => {
    const interval = setInterval(() => {
      if (uploadsRef.current.some((u) => u.status === "processing" || u.status === "pending")) {
        fetchUploads();
      }
    }, 3000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this upload and all its transactions?")) return;
    setDeletingId(id);
    try {
      await deleteUpload(id);
      setUploads((prev) => prev.filter((u) => u.id !== id));
    } catch (e) {
      console.error(e);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Upload Bank Statement</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload PDF, Excel, or CSV bank statements. AI will auto-classify each transaction.
        </p>
        {businessName && (
          <span className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-0.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full border border-indigo-100">
            <Building2 size={11} />
            Uploading to: {businessName}
          </span>
        )}
      </div>

      {/* Instructions */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-sm text-blue-800">
        <p className="font-semibold mb-1">Supported formats</p>
        <ul className="list-disc list-inside space-y-0.5 text-blue-700">
          <li>
            <strong>PDF</strong> — Most Indian bank statement PDFs (HDFC, ICICI, SBI, Axis, Kotak)
          </li>
          <li>
            <strong>Excel (XLS/XLSX)</strong> — Exported bank statements with Date, Narration, Debit, Credit columns
          </li>
          <li>
            <strong>CSV</strong> — Comma-separated export with standard column names
          </li>
        </ul>
      </div>

      {/* Upload Zone */}
      <div className="mb-8">
        <UploadZone
          onUploadComplete={() => {
            fetchUploads();
          }}
        />
      </div>

      {/* Upload History */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-800">Upload History</h2>
          <button
            onClick={fetchUploads}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {loadingUploads ? (
          <div className="text-center py-8 text-gray-400">Loading…</div>
        ) : uploads.length === 0 ? (
          <div className="text-center py-8 text-gray-400 border border-dashed border-gray-200 rounded-xl">
            No uploads yet
          </div>
        ) : (
          <div className="space-y-2">
            {uploads.map((upload) => (
              <div
                key={upload.id}
                className="bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-4"
              >
                <FileTypeIcon type={upload.file_type} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800 truncate">
                    {upload.original_filename}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>{new Date(upload.created_at).toLocaleString("en-IN")}</span>
                    {upload.status === "completed" && (
                      <>
                        <span>·</span>
                        <span className="text-green-600">{upload.row_count} rows</span>
                        <span>·</span>
                        <span>{upload.mapped_count} mapped</span>
                        {upload.unmapped_count > 0 && (
                          <>
                            <span>·</span>
                            <span className="text-amber-600">{upload.unmapped_count} unmapped</span>
                          </>
                        )}
                      </>
                    )}
                    {upload.status === "failed" && upload.error_message && (
                      <span className="text-red-600 truncate max-w-sm" title={upload.error_message}>
                        Error: {upload.error_message}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-sm">
                    <StatusIcon status={upload.status} />
                    <span
                      className={clsx("capitalize", {
                        "text-green-600": upload.status === "completed",
                        "text-red-600": upload.status === "failed",
                        "text-indigo-600": upload.status === "processing",
                        "text-gray-400": upload.status === "pending",
                      })}
                    >
                      {upload.status}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDelete(upload.id)}
                    disabled={deletingId === upload.id}
                    className="p-1.5 text-gray-300 hover:text-red-500 transition-colors"
                    title="Delete upload"
                  >
                    {deletingId === upload.id ? (
                      <Loader size={15} className="animate-spin" />
                    ) : (
                      <Trash2 size={15} />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
