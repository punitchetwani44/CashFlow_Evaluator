"use client";
import { useState } from "react";
import { Calendar, ChevronDown } from "lucide-react";
import { DateRange } from "@/lib/api";

interface Props {
  value: DateRange;
  onChange: (range: DateRange) => void;
}

// Returns YYYY-MM string for a given date
function toYearMonth(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Build predefined ranges relative to today
function buildPresets(): { label: string; dateFrom: string; dateTo: string }[] {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth(); // 0-indexed

  // Quarter helper
  const quarterStart = (month0: number) => new Date(y, Math.floor(month0 / 3) * 3, 1);
  const quarterEnd   = (month0: number) => new Date(y, Math.floor(month0 / 3) * 3 + 3, 0);

  // Indian FY: Apr 1 – Mar 31
  const fyStart = m >= 3 ? new Date(y, 3, 1) : new Date(y - 1, 3, 1);
  const fyEnd   = m >= 3 ? new Date(y + 1, 2, 28) : new Date(y, 2, 31);
  const prevFyStart = new Date(fyStart.getFullYear() - 1, 3, 1);
  const prevFyEnd   = new Date(fyStart.getFullYear(), 2, 31);

  // Previous quarter
  let prevQM = m - 3;
  let prevQY = y;
  if (prevQM < 0) { prevQM += 12; prevQY -= 1; }
  const prevQDate = new Date(prevQY, prevQM, 1);

  return [
    {
      label: "This Month",
      dateFrom: toYearMonth(new Date(y, m, 1)),
      dateTo:   toYearMonth(new Date(y, m, 1)),
    },
    {
      label: "Last Month",
      dateFrom: toYearMonth(new Date(y, m - 1, 1)),
      dateTo:   toYearMonth(new Date(y, m - 1, 1)),
    },
    {
      label: "This Quarter",
      dateFrom: toYearMonth(quarterStart(m)),
      dateTo:   toYearMonth(quarterEnd(m)),
    },
    {
      label: "Last Quarter",
      dateFrom: toYearMonth(new Date(prevQY, Math.floor(prevQM / 3) * 3, 1)),
      dateTo:   toYearMonth(new Date(prevQY, Math.floor(prevQM / 3) * 3 + 3, 0)),
    },
    {
      label: "This Year",
      dateFrom: `${y}-01`,
      dateTo:   `${y}-12`,
    },
    {
      label: "Last Year",
      dateFrom: `${y - 1}-01`,
      dateTo:   `${y - 1}-12`,
    },
    {
      label: "This Financial Year",
      dateFrom: toYearMonth(fyStart),
      dateTo:   toYearMonth(fyEnd),
    },
    {
      label: "Last Financial Year",
      dateFrom: toYearMonth(prevFyStart),
      dateTo:   toYearMonth(prevFyEnd),
    },
  ];
}

// Count months between two YYYY-MM strings (inclusive)
function monthsBetween(from: string, to: string): number {
  const [fy, fm] = from.split("-").map(Number);
  const [ty, tm] = to.split("-").map(Number);
  return (ty - fy) * 12 + (tm - fm) + 1;
}

export default function DateRangeSelector({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [customError, setCustomError] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  const presets = buildPresets();

  const selectPreset = (preset: { label: string; dateFrom: string; dateTo: string }) => {
    setShowCustom(false);
    setCustomError("");
    onChange({ dateFrom: preset.dateFrom, dateTo: preset.dateTo, label: preset.label });
    setOpen(false);
  };

  const applyCustom = () => {
    setCustomError("");
    if (!customFrom || !customTo) {
      setCustomError("Please select both start and end months.");
      return;
    }
    if (customFrom > customTo) {
      setCustomError("Start month must be before end month.");
      return;
    }
    if (monthsBetween(customFrom, customTo) > 24) {
      setCustomError("Custom range cannot exceed 24 months.");
      return;
    }
    onChange({ dateFrom: customFrom, dateTo: customTo, label: "Custom Range" });
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 pl-3 pr-2.5 py-2 border border-gray-200 rounded-lg text-sm font-medium bg-white hover:border-indigo-300 focus:outline-none focus:border-indigo-400 transition"
      >
        <Calendar size={14} className="text-gray-400" />
        <span className="text-gray-700">{value.label}</span>
        <ChevronDown
          size={13}
          className={`text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
          {/* Preset list */}
          {presets.map((p) => (
            <button
              key={p.label}
              onClick={() => selectPreset(p)}
              className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition ${
                value.label === p.label && !showCustom
                  ? "text-indigo-600 font-semibold bg-indigo-50"
                  : "text-gray-700"
              }`}
            >
              {p.label}
              <span className="text-xs text-gray-400 ml-2 font-normal">
                {p.dateFrom === p.dateTo ? p.dateFrom : `${p.dateFrom} – ${p.dateTo}`}
              </span>
            </button>
          ))}

          {/* Custom Range toggle */}
          <button
            onClick={() => setShowCustom((v) => !v)}
            className={`w-full text-left px-4 py-2.5 text-sm border-t border-gray-100 hover:bg-gray-50 transition ${
              showCustom ? "text-indigo-600 font-semibold bg-indigo-50" : "text-gray-700"
            }`}
          >
            Custom Range
          </button>

          {showCustom && (
            <div className="px-4 pb-4 pt-2 bg-gray-50 border-t border-gray-100">
              <div className="space-y-2">
                <div>
                  <label className="text-xs text-gray-500 font-medium">From</label>
                  <input
                    type="month"
                    value={customFrom}
                    onChange={(e) => { setCustomFrom(e.target.value); setCustomError(""); }}
                    className="w-full mt-1 px-2 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-indigo-400"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 font-medium">To</label>
                  <input
                    type="month"
                    value={customTo}
                    onChange={(e) => { setCustomTo(e.target.value); setCustomError(""); }}
                    className="w-full mt-1 px-2 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-indigo-400"
                  />
                </div>
                {customError && (
                  <p className="text-xs text-red-600">{customError}</p>
                )}
                <button
                  onClick={applyCustom}
                  className="w-full py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition"
                >
                  Apply
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
