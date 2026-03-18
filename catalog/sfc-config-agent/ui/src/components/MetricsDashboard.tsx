/**
 * MetricsDashboard — Chart.js time-series dashboard for SFC CloudWatch metrics.
 *
 * Renders a Line chart with one series per discovered SFC metric under the
 * "LaunchPackage" dimension. Supports category tabs: Target | Core | Adapter | All.
 * Default category is "Target" (SFC ingest / write health).
 *
 * Auto-refreshes every 60 seconds.
 */
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Filler,
  type ChartOptions,
  type TooltipItem,
} from "chart.js";
import "chartjs-adapter-date-fns";
import { Line } from "react-chartjs-2";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getPackageMetrics, type MetricsCategory } from "../api/client";

// Register all required Chart.js components (must be done once globally)
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Filler
);

const CATEGORIES: { label: string; value: MetricsCategory }[] = [
  { label: "Target", value: "Target" },
  { label: "Core", value: "Core" },
  { label: "Adapter", value: "Adapter" },
  { label: "All", value: "All" },
];

const LOOKBACK_OPTIONS = [
  { label: "15 min", value: 15 },
  { label: "30 min", value: 30 },
  { label: "1 h", value: 60 },
  { label: "3 h", value: 180 },
];

interface Props {
  packageId: string;
}

export default function MetricsDashboard({ packageId }: Props) {
  const [category, setCategory] = useState<MetricsCategory>("Target");
  const [lookback, setLookback] = useState(15);

  const { data, isLoading, isError, dataUpdatedAt, refetch, isFetching } =
    useQuery({
      queryKey: ["metrics", packageId, category, lookback],
      queryFn: () => getPackageMetrics(packageId, category, lookback),
      refetchInterval: 60_000, // auto-refresh every 60 s
      staleTime: 30_000,
    });

  const hasData = Array.isArray(data) && data.length > 0;
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : null;

  const chartOptions: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          color: "#94a3b8", // slate-400
          font: { size: 11 },
          boxWidth: 12,
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: "#1e293b",
        titleColor: "#e2e8f0",
        bodyColor: "#94a3b8",
        borderColor: "#334155",
        borderWidth: 1,
        callbacks: {
          title: (items: TooltipItem<"line">[]) => {
            if (!items[0]) return "";
            const raw = items[0].raw as { x: string; y: number };
            return new Date(raw.x).toLocaleTimeString();
          },
          label: (item: TooltipItem<"line">) => {
            const raw = item.raw as { x: string; y: number };
            return ` ${item.dataset.label}: ${raw.y}`;
          },
        },
      },
    },
    scales: {
      x: {
        type: "time",
        time: {
          unit: "minute",
          tooltipFormat: "HH:mm:ss",
          displayFormats: { minute: "HH:mm" },
        },
        ticks: { color: "#64748b", maxTicksLimit: 8, font: { size: 10 } },
        grid: { color: "#1e293b" },
      },
      y: {
        ticks: { color: "#64748b", font: { size: 10 } },
        grid: { color: "#1e293b" },
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="card space-y-3 border border-slate-700/50">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-4 h-4 text-emerald-400 shrink-0"
          >
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <p className="text-xs font-medium text-slate-300">CloudWatch Metrics</p>
          {lastUpdated && (
            <span className="text-[10px] text-slate-500 italic">
              updated {lastUpdated}
            </span>
          )}
          {isFetching && (
            <span className="w-3 h-3 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin" />
          )}
        </div>

        {/* Lookback selector */}
        <div className="flex items-center gap-1">
          {LOOKBACK_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setLookback(opt.value)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                lookback === opt.value
                  ? "bg-slate-600 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
          <button
            onClick={() => refetch()}
            title="Refresh now"
            className="ml-1 p-1 rounded text-slate-500 hover:text-slate-300 transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-3 h-3"
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Category tab bar */}
      <div className="flex items-center gap-1 border-b border-slate-700/50 pb-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategory(cat.value)}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              category === cat.value
                ? "bg-emerald-900/50 text-emerald-300 border border-emerald-700/60"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {cat.label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-slate-600 italic">
          {category === "Target"
            ? "write / ingest health"
            : category === "Core"
            ? "SFC core pipeline"
            : category === "Adapter"
            ? "adapter / read health"
            : "all SFC metrics"}
        </span>
      </div>

      {/* Chart area */}
      <div className="relative" style={{ height: 260 }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="w-5 h-5 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin" />
          </div>
        )}

        {isError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-xs text-red-400">Failed to load metrics.</p>
          </div>
        )}

        {!isLoading && !isError && !hasData && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-8 h-8 text-slate-700"
            >
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <p className="text-xs text-slate-600">
              No <span className="text-slate-500">{category}</span> metrics yet
              for the last {lookback} min.
            </p>
            <p className="text-[10px] text-slate-700">
              Start the launch package to begin emitting SFC metrics.
            </p>
          </div>
        )}

        {!isLoading && hasData && (
          <Line
            data={{ datasets: data! }}
            options={chartOptions}
          />
        )}
      </div>
    </div>
  );
}
