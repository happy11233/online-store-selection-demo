import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const colors = ["#f04438", "#f79009", "#12b76a", "#6941c6"];

function shortDate(value) {
  return String(value || "").slice(5);
}

export function HotspotTrendChart({ data = [], lines = [] }) {
  if (!data.length || !lines.length) return <div className="chart-empty">暂无趋势数据</div>;
  return <ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 2 }}><CartesianGrid stroke="#f2f4f7" vertical={false} /><XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#98a2b3" }} /><YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#98a2b3" }} /><Tooltip labelFormatter={(label) => `日期 ${label}`} formatter={(value, name) => [value, lines.find((line) => line.key === name)?.label || name]} contentStyle={{ border: "1px solid #eaecf0", borderRadius: 6, fontSize: 11 }} /><Legend iconType="circle" iconSize={6} wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />{lines.map((line, index) => <Line key={line.key} type="monotone" dataKey={line.key} name={line.label} stroke={colors[index % colors.length]} strokeWidth={2} dot={{ r: 2, strokeWidth: 0 }} activeDot={{ r: 4 }} />)}</LineChart></ResponsiveContainer>;
}

export function FeedbackTrendChart({ data = [] }) {
  if (!data.length) return <div className="chart-empty">暂无回流数据</div>;
  return <ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 2 }}><CartesianGrid stroke="#f2f4f7" vertical={false} /><XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#98a2b3" }} /><YAxis yAxisId="count" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#98a2b3" }} /><YAxis yAxisId="rate" orientation="right" domain={[0, "auto"]} tickFormatter={(value) => `${(value * 100).toFixed(0)}%`} tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#98a2b3" }} /><Tooltip labelFormatter={(label) => `日期 ${label}`} formatter={(value, name) => { const labels = { impressions: "曝光", clicks: "点击", orders: "成交", ctr: "CTR", cvr: "CVR" }; return [name === "ctr" || name === "cvr" ? `${(Number(value) * 100).toFixed(1)}%` : Number(value).toLocaleString(), labels[name] || name]; }} contentStyle={{ border: "1px solid #eaecf0", borderRadius: 6, fontSize: 11 }} /><Legend iconType="circle" iconSize={6} wrapperStyle={{ fontSize: 10, paddingTop: 8 }} /><Line yAxisId="count" type="monotone" dataKey="impressions" name="曝光" stroke="#98a2b3" strokeWidth={1.5} dot={false} /><Line yAxisId="count" type="monotone" dataKey="clicks" name="点击" stroke="#f04438" strokeWidth={2} dot={false} /><Line yAxisId="count" type="monotone" dataKey="orders" name="成交" stroke="#12b76a" strokeWidth={2} dot={false} /><Line yAxisId="rate" type="monotone" dataKey="ctr" name="CTR" stroke="#6941c6" strokeWidth={1.5} dot={false} strokeDasharray="4 4" /></LineChart></ResponsiveContainer>;
}
