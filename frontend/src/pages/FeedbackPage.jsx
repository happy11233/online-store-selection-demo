import React, { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Eye, MousePointer2, RefreshCw, Send, ShoppingBag, Wallet } from "lucide-react";
import { FeedbackTrendChart } from "../components/charts";
import { Badge, Button, Card, Spinner } from "../components/ui";
import { useAuth } from "../auth-context";
import {
  createTrainingSnapshot,
  getFeedbackRecords,
  getFeedbackSummary,
  getFeedbackTrends,
  getHotspots,
  getLoopStatus,
  getProducts,
  getTrainingSnapshots,
  submitFeedback,
} from "../lib/api";

const pct = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const money = (value) => `¥${Number(value || 0).toFixed(2)}`;

function FeedbackStat({ icon: Icon, label, value, detail, tone = "red" }) {
  return <div className="stat"><div className={`stat-icon ${tone}`}><Icon size={17} /></div><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></div>;
}

function FeedbackForm({ form, products, hotspots, productsLoading, mutation, notice, onChange, onSubmit, canOperate }) {
  const errorText = mutation.error?.response?.data?.detail || "提交失败，请检查数据关系。";
  return <Card className="feedback-form-card"><div className="section-heading"><div><p className="eyebrow">SIMULATE EVENT</p><h3>新增回流样本</h3></div><Send size={18} /></div><p className="muted">模拟运营投放后的真实漏斗数据，提交后立即进入复盘指标。</p><form className="feedback-form" onSubmit={onSubmit}><label className="form-field"><span>商品</span><select value={form.product_id} onChange={(event) => onChange("product_id", event.target.value)} disabled={productsLoading}>{products.map((item) => <option key={item.product_id} value={item.product_id}>{item.product_id} · {item.title}</option>)}</select></label><label className="form-field"><span>关联热点</span><select value={form.hotspot_id} onChange={(event) => onChange("hotspot_id", event.target.value)}>{hotspots.map((item) => <option key={item.hotspot_id} value={item.hotspot_id}>#{item.keyword}</option>)}</select></label><label className="form-field"><span>事件 ID <em>可选，用于演示去重</em></span><input value={form.event_id} placeholder="例如 campaign-demo-001" onChange={(event) => onChange("event_id", event.target.value)} /></label><div className="form-grid"><label className="form-field"><span>曝光数</span><input type="number" min="0" value={form.impressions} onChange={(event) => onChange("impressions", event.target.value)} /></label><label className="form-field"><span>点击数</span><input type="number" min="0" value={form.clicks} onChange={(event) => onChange("clicks", event.target.value)} /></label><label className="form-field"><span>成交数</span><input type="number" min="0" value={form.orders} onChange={(event) => onChange("orders", event.target.value)} /></label><label className="form-field"><span>退款数</span><input type="number" min="0" value={form.refunds} onChange={(event) => onChange("refunds", event.target.value)} /></label><label className="form-field"><span>成交 GMV</span><input type="number" min="0" step="0.01" value={form.revenue} onChange={(event) => onChange("revenue", event.target.value)} /></label></div>{mutation.isError && <p className="form-error">{errorText}</p>}{notice && <p className="form-success">{notice}</p>}<Button className="full" type="submit" disabled={!canOperate || mutation.isPending}>{mutation.isPending ? <Spinner /> : <RefreshCw size={15} />}提交回流样本</Button></form></Card>;
}

function FeedbackTable({ records, hotspots, isLoading }) {
  if (isLoading) return <div className="loading"><Spinner /></div>;
  if (!records.length) return <div className="empty"><span>暂无回流样本</span></div>;
  return <div className="table-wrap"><table><thead><tr><th>日期</th><th>商品</th><th>热点</th><th>曝光</th><th>点击 / CTR</th><th>成交 / CVR</th><th>退款率</th><th>GMV</th><th>预估佣金</th></tr></thead><tbody>{records.map((row, index) => <tr key={`${row.event_id || row.product_id}-${row.recorded_at}-${index}`}><td><span className="date-text">{String(row.recorded_at || "").slice(0, 10)}</span></td><td><div className="feedback-product"><strong>{row.title}</strong><span>{row.product_id} · {row.category}</span></div></td><td><Badge tone="gray">{hotspots.find((hot) => hot.hotspot_id === row.hotspot_id)?.keyword || row.hotspot_id || "—"}</Badge></td><td>{Number(row.impressions).toLocaleString()}</td><td><strong>{Number(row.clicks).toLocaleString()}</strong><span className="subline">{pct(row.ctr)}</span></td><td><strong>{Number(row.orders).toLocaleString()}</strong><span className="subline">{pct(row.cvr)}</span></td><td>{pct(row.refund_rate)}</td><td>{money(row.revenue)}</td><td className="green-text">{money(row.estimated_commission)}</td></tr>)}</tbody></table></div>;
}

function SnapshotHistory({ snapshots }) {
  if (!snapshots?.length) return null;
  return <Card className="snapshot-card"><div className="section-heading"><div><p className="eyebrow">TRAINING SNAPSHOTS</p><h3>训练快照记录</h3></div><Badge tone="gray">Demo 模拟评估</Badge></div><div className="snapshot-list">{snapshots.slice(0, 5).map((snapshot) => <div className="snapshot-row" key={snapshot.snapshot_id}><div><strong>{snapshot.snapshot_id}</strong><span>{snapshot.created_at} · {snapshot.sample_count} 条样本</span></div><Badge tone={snapshot.status === "ready" ? "green" : "gray"}>{snapshot.status === "ready" ? "达到训练门槛" : "继续积累样本"}</Badge><small>{snapshot.metrics ? `PR-AUC ${snapshot.metrics.pr_auc} · Top-K ${snapshot.metrics.top_k_hit_rate}` : "尚未运行真实训练"}</small></div>)}</div></Card>;
}

export default function FeedbackPage() {
  const { canOperate } = useAuth();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ event_id: "", product_id: params.get("product_id") || "", hotspot_id: params.get("hotspot_id") || "", recommendation_id: params.get("recommendation_id") || "", impressions: 10000, clicks: 800, orders: 40, refunds: 0, revenue: 1600 });
  const [notice, setNotice] = useState("");
  const { data: productsData, isLoading: productsLoading } = useQuery({ queryKey: ["products"], queryFn: getProducts });
  const { data: hotspotsData } = useQuery({ queryKey: ["hotspots"], queryFn: getHotspots });
  const { data: summaryData, isLoading: summaryLoading } = useQuery({ queryKey: ["feedback-summary"], queryFn: () => getFeedbackSummary() });
  const { data: recordsData, isLoading: recordsLoading } = useQuery({ queryKey: ["feedback-records"], queryFn: () => getFeedbackRecords() });
  const { data: trendsData } = useQuery({ queryKey: ["feedback-trends"], queryFn: () => getFeedbackTrends() });
  const { data: loopData } = useQuery({ queryKey: ["loop-status"], queryFn: getLoopStatus });
  const { data: snapshotsData } = useQuery({ queryKey: ["training-snapshots"], queryFn: getTrainingSnapshots });
  const mutation = useMutation({ mutationFn: submitFeedback, onSuccess: (result) => { if (result.data.duplicate) { setNotice("重复事件已忽略，指标未变"); return; } queryClient.invalidateQueries({ queryKey: ["feedback-summary"] }); queryClient.invalidateQueries({ queryKey: ["feedback-records"] }); queryClient.invalidateQueries({ queryKey: ["feedback-trends"] }); queryClient.invalidateQueries({ queryKey: ["loop-status"] }); setNotice("回流样本已写入，指标已刷新"); } });
  const snapshotMutation = useMutation({ mutationFn: createTrainingSnapshot, onSuccess: (result) => { queryClient.invalidateQueries({ queryKey: ["loop-status"] }); queryClient.invalidateQueries({ queryKey: ["training-snapshots"] }); setNotice(result.data.status === "ready" ? "Demo 训练快照已生成，评估指标为模拟值" : "Demo 训练快照已生成，仍需积累回流样本"); } });
  const products = productsData?.data || [];
  const hotspots = hotspotsData?.data || [];
  const summary = summaryData?.data || {};
  const records = recordsData?.data || [];
  const loop = loopData?.data || {};
  const snapshots = snapshotsData?.data || [];

  useEffect(() => { setForm((current) => ({ ...current, product_id: current.product_id || products[0]?.product_id || "", hotspot_id: current.hotspot_id || hotspots[0]?.hotspot_id || "" })); }, [products, hotspots]);
  const setField = (key, value) => setForm((current) => ({ ...current, [key]: ["event_id", "product_id", "hotspot_id", "recommendation_id"].includes(key) ? value : Number(value) }));
  const handleSubmit = (event) => { event.preventDefault(); setNotice(""); mutation.mutate(form); };

  return <div className="content"><div className="page-intro"><div><p className="eyebrow">FEEDBACK LOOP</p><h2>投放回流</h2><p className="muted">把曝光、点击和成交还给模型，观察推荐是否真的产生业务结果。</p></div><Badge tone="green"><span className="live-dot" /> Demo 样本可追加</Badge></div><div className="stats feedback-stats"><FeedbackStat icon={Eye} label="总曝光" value={summaryLoading ? "—" : Number(summary.impressions || 0).toLocaleString()} detail="样本累计" /><FeedbackStat icon={MousePointer2} label="CTR" value={summaryLoading ? "—" : pct(summary.ctr)} detail={`${Number(summary.clicks || 0).toLocaleString()} 次点击`} tone="teal" /><FeedbackStat icon={ShoppingBag} label="CVR" value={summaryLoading ? "—" : pct(summary.cvr)} detail={`${Number(summary.orders || 0).toLocaleString()} 笔成交`} tone="amber" /><FeedbackStat icon={Wallet} label="预估佣金" value={summaryLoading ? "—" : money(summary.estimated_commission)} detail={`GMV ${money(summary.gmv)}`} tone="purple" /></div><div className="feedback-grid"><Card className="chart-card"><div className="section-heading"><div><p className="eyebrow">PERFORMANCE TREND</p><h3>投放表现趋势</h3></div><Badge tone="gray">按日聚合</Badge></div><div className="chart-wrap"><FeedbackTrendChart data={trendsData?.data || []} /></div></Card><FeedbackForm form={form} products={products} hotspots={hotspots} productsLoading={productsLoading} mutation={mutation} notice={notice} onChange={setField} onSubmit={handleSubmit} canOperate={canOperate} /></div><Card className="feedback-table-card"><div className="section-heading"><div><p className="eyebrow">EVENT LOG</p><h3>最近投放样本</h3></div><span className="muted">共 {records.length} 条</span></div><FeedbackTable records={records} hotspots={hotspots} isLoading={recordsLoading} /></Card><div className="loop-status-card"><div><p className="eyebrow">MODEL ITERATION</p><strong>{loop.model_version || "加载中"}</strong><span>{loop.next_action || "正在检查训练条件"}</span><small className="snapshot-count">已生成 {snapshots.length} 个训练快照</small></div><div className={`iteration-meter ${loop.training_ready ? "ready" : ""}`}><strong>{loop.feedback_sample_count || 0} / {loop.min_training_samples || 20}</strong><small>回流样本 / 训练门槛</small></div><Button variant="secondary" className="small-button" onClick={() => snapshotMutation.mutate({ note: "运营 Demo 手动触发" })} disabled={!canOperate || snapshotMutation.isPending}>{snapshotMutation.isPending ? <Spinner /> : <RefreshCw size={13} />}生成快照</Button></div><SnapshotHistory snapshots={snapshots} /><div className="loop-strip"><div className="loop-step done"><span>01</span><strong>投放执行</strong><small>记录曝光点击</small></div><span className="loop-arrow">→</span><div className="loop-step done"><span>02</span><strong>结果回流</strong><small>提交漏斗样本</small></div><span className="loop-arrow">→</span><div className="loop-step"><span>03</span><strong>模型迭代</strong><small>{loop.next_action || "待积累样本"}</small></div></div></div>;
}
