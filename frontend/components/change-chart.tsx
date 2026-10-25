"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { metricLabel } from "@/lib/format";

export type ChangePoint = {
  metric: string;
  change: number | null;
  unit: string;
};

export function ChangeChart({ data }: { data: ChangePoint[] }) {
  const points = data
    .filter((item): item is ChangePoint & { change: number } => item.change !== null)
    .map((item) => ({ ...item, label: metricLabel(item.metric) }));

  if (points.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-slate-700 text-sm text-slate-500">
        No comparable metrics. Values are unavailable, not zero.
      </div>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={{ stroke: "#1e293b" }}
            tickLine={false}
            interval={0}
            angle={-12}
            height={50}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            unit="%"
          />
          <ReferenceLine y={0} stroke="#64748b" />
          <Tooltip
            cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
            contentStyle={{
              background: "#0b1220",
              border: "1px solid #1e293b",
              borderRadius: 12,
              color: "#e2e8f0",
              fontSize: 12,
            }}
            formatter={(value) => {
              if (typeof value !== "number") return ["Unavailable", "change"];
              return [`${value >= 0 ? "+" : ""}${value.toFixed(2)}%`, "change"];
            }}
          />
          <Bar dataKey="change" radius={[6, 6, 0, 0]} maxBarSize={64}>
            {points.map((point) => (
              <Cell key={point.metric} fill={point.change >= 0 ? "#34d399" : "#fb7185"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
