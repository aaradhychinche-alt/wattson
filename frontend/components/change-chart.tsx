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
      <div className="flex h-64 items-center justify-center rounded-[16px] border border-dashed border-[#292d30] font-mono text-xs text-[#a1a4a5]">
        No comparable metrics. Values are unavailable, not zero.
      </div>
    );
  }

  return (
    <div className="h-72 w-full pt-4 font-mono">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={{ top: 12, right: 12, left: -10, bottom: 8 }}>
          <CartesianGrid stroke="#292d30" strokeDasharray="2 2" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#a1a4a5", fontSize: 11, fontFamily: "monospace" }}
            axisLine={{ stroke: "#292d30" }}
            tickLine={false}
            interval={0}
            angle={-12}
            height={50}
          />
          <YAxis
            tick={{ fill: "#a1a4a5", fontSize: 11, fontFamily: "monospace" }}
            axisLine={false}
            tickLine={false}
            unit="%"
          />
          <ReferenceLine y={0} stroke="#292d30" strokeWidth={1.5} />
          <Tooltip
            cursor={{ fill: "rgba(41, 45, 48, 0.4)" }}
            contentStyle={{
              background: "#000000",
              border: "1px solid #292d30",
              borderRadius: 6,
              color: "#f0f0f0",
              fontSize: 12,
              fontFamily: "monospace",
              padding: "8px 12px",
            }}
            formatter={(value) => {
              if (typeof value !== "number") return ["Unavailable", "change"];
              return [`${value >= 0 ? "+" : ""}${value.toFixed(2)}%`, "variance"];
            }}
          />
          <Bar dataKey="change" radius={[4, 4, 0, 0]} maxBarSize={48}>
            {points.map((point) => (
              <Cell
                key={point.metric}
                fill={point.change >= 0 ? "#3ad389" : "#ff9592"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
