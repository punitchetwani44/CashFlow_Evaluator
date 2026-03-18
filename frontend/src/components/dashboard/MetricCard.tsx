"use client";
import { ReactNode } from "react";
import clsx from "clsx";

interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon: ReactNode;
  color?: "green" | "red" | "indigo" | "amber";
  trend?: { value: number; label: string };
}

const colorMap = {
  green: { bg: "bg-green-50", icon: "bg-green-100 text-green-600", text: "text-green-700" },
  red: { bg: "bg-red-50", icon: "bg-red-100 text-red-600", text: "text-red-700" },
  indigo: { bg: "bg-indigo-50", icon: "bg-indigo-100 text-indigo-600", text: "text-indigo-700" },
  amber: { bg: "bg-amber-50", icon: "bg-amber-100 text-amber-600", text: "text-amber-700" },
};

export default function MetricCard({
  label,
  value,
  subValue,
  icon,
  color = "indigo",
  trend,
}: MetricCardProps) {
  const c = colorMap[color];
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500 mb-1">{label}</p>
          <p className={clsx("text-2xl font-bold", c.text)}>{value}</p>
          {subValue && (
            <p className="text-xs text-gray-400 mt-1">{subValue}</p>
          )}
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <span
                className={clsx(
                  "text-xs font-medium",
                  trend.value >= 0 ? "text-green-600" : "text-red-600"
                )}
              >
                {trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value).toFixed(1)}%
              </span>
              <span className="text-xs text-gray-400">{trend.label}</span>
            </div>
          )}
        </div>
        <div className={clsx("p-3 rounded-lg", c.icon)}>{icon}</div>
      </div>
    </div>
  );
}
