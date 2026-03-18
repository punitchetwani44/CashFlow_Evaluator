"use client";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Building2, AlertTriangle } from "lucide-react";
import { BusinessAccount } from "@/lib/api";

interface Props {
  userBAs: BusinessAccount[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}

export default function BusinessSelector({ userBAs, selectedIds, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Hidden for single-BA users
  if (userBAs.length <= 1) return null;

  const allSelected = selectedIds.length === userBAs.length;
  const noneSelected = selectedIds.length === 0;

  const buttonLabel = noneSelected
    ? "No Business"
    : allSelected
    ? "All Businesses"
    : selectedIds.length === 1
    ? userBAs.find((b) => b.id === selectedIds[0])?.name ?? "1 Business"
    : `${selectedIds.length} Businesses`;

  const toggleAll = () => {
    if (allSelected) {
      // Keep at least one selected — default to first
      onChange([userBAs[0].id]);
    } else {
      onChange(userBAs.map((b) => b.id));
    }
  };

  const toggleOne = (id: number) => {
    if (selectedIds.includes(id)) {
      // Don't allow de-selecting the last one
      if (selectedIds.length === 1) return;
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 pl-3 pr-2.5 py-2 border border-gray-200 rounded-lg text-sm font-medium bg-white hover:border-indigo-300 focus:outline-none focus:border-indigo-400 transition"
      >
        <Building2 size={14} className="text-gray-400" />
        <span className="text-gray-700">{buttonLabel}</span>
        <ChevronDown
          size={13}
          className={`text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
          {/* Select All */}
          <label className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100">
            <input
              type="checkbox"
              className="rounded text-indigo-600"
              checked={allSelected}
              onChange={toggleAll}
            />
            <span className="text-sm font-semibold text-gray-700">All Businesses</span>
          </label>

          {/* Individual BAs */}
          <div className="max-h-52 overflow-y-auto">
            {userBAs.map((ba) => (
              <label
                key={ba.id}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  className="rounded text-indigo-600"
                  checked={selectedIds.includes(ba.id)}
                  onChange={() => toggleOne(ba.id)}
                />
                <div className="min-w-0">
                  <p className="text-sm text-gray-700 truncate">{ba.name}</p>
                  {!ba.is_active && (
                    <p className="text-xs text-gray-400">Inactive</p>
                  )}
                </div>
              </label>
            ))}
          </div>

          {/* Performance warning */}
          {selectedIds.length > 10 && (
            <div className="flex items-start gap-2 px-4 py-2.5 bg-amber-50 border-t border-amber-100">
              <AlertTriangle size={14} className="text-amber-500 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-amber-700">
                Selecting many businesses may slow down loading.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
