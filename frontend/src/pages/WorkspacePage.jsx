import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronRight, Download, Filter, Gauge, RefreshCw, Search, Settings2, Sparkles, TrendingUp } from "lucide-react";
import { Badge, Button, Card, Modal, Spinner } from "../components/ui";
import { useAuth } from "../auth-context";
import { createContentDraft, exportUrl, getDataQuality, getHotspots, getModels, getProduct, getRules, recommend, updateRules } from "../lib/api";

const money = (value) => `¥${Number(value || 0).toFixed(2)}`;
const pct = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;

function Stat({ icon: Icon, label, value, detail, tone = "red" }) {
  return <div className="stat"><div className={`stat-icon ${tone}`}><Icon size={17} /></div><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></div>;
}

function HotspotList({ hotspots, selected, onSelect }) {
  return <div className="hotspot-list">{hotspots?.map((hot, index) => <button key={hot.hotspot_id} className={`hotspot ${selected === hot.hotspot_id ? "active" : ""}`} onClick={() => onSelect(hot.hotspot_id)}><div className="hotspot-rank">{String(index + 1).padStart(2, "0")}</div><div className="hotspot-main"><div className="hotspot-title"><strong>#{hot.keyword}</strong><Badge tone={index < 2 ? "red" : "gray"}>{hot.category}</Badge></div><div className="heatline"><span className="heat-track"><i style={{ width: `${Math.min(100, hot.heat_value)}%` }} /></span><span>{hot.heat_value}</span><span className="rise">↗ {pct(hot.rise_rate)}</span></div></div><ChevronRight size={16} className="chevron" /></button>)}</div>;
}

function RecommendationTable({ rows, onOpen, onInsight, onFeedback, onDraft, canOperate }) {
  if (!rows?.length) return <div className="empty"><Sparkles size={24} /><strong>暂无符合条件的商品</strong><span>可以降低规则阈值，或切换一个热点重试。</span></div>;
  return <div className="table-wrap"><table><thead><tr><th>商品</th><th>类目 / 售价</th><th>佣金</th><th>AI 综合分</th><th>热点匹配</th><th>内容建议</th><th>动作</th></tr></thead><tbody>{rows.map((row) => <tr key={row.product_id}><td><div className="product-cell"><img src={row.image_url} alt="" /><div><strong>{row.title}</strong><span>{row.product_id} · {row.category}</span></div></div></td><td><strong>{money(row.price)}</strong><span className="subline">销量 {Number(row.estimated_sales).toLocaleString()}</span></td><td><span className="commission">{pct(row.commission_rate)}</span><span className="subline">退货 {pct(row.return_rate)}</span></td><td><div className="score"><strong>{row.final_score}</strong><div className="scorebar"><i style={{ width: `${row.final_score}%` }} /></div></div></td><td><Badge tone={row.semantic_score >= 60 ? "green" : "gray"}>{row.semantic_score} 分</Badge><span className="subline clamp">{row.match_reason}</span></td><td><span className="topic">{row.content_topic}</span></td><td><div className="row-actions"><button className="more" onClick={() => onOpen(row)}>详情</button><button className="more" onClick={() => onInsight(row)}>解释</button>{canOperate && <><button className="more" onClick={() => onDraft(row)}>内容</button><button className="more" onClick={() => onFeedback(row)}>回流</button></>}</div></td></tr>)}</tbody></table></div>;
}

function FilterSummary({ filtered }) {
  if (!filtered?.length) return null;
  return <div className="filter-summary"><div><strong>已过滤 {filtered.length} 件</strong><span>硬规则和 AI 阈值原因</span></div><div className="filter-reasons">{filtered.map((item) => <span key={`${item.product_id}-${item.reason}`}><b>{item.product_id}</b>{item.reason}</span>)}</div></div>;
}

function RulePanel({ rules, onSaved, canEdit }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(rules);
  useEffect(() => setDraft(rules), [rules]);
  const mutation = useMutation({ mutationFn: updateRules, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["rules"] }); onSaved(); } });
  const field = (key, label, unit, step = "0.01", percentage = false) => <label className="form-field"><span>{label}<em>{unit}</em></span><input disabled={!canEdit} type="number" step={step} value={percentage ? Number(draft?.[key] ?? 0) * 100 : (draft?.[key] ?? "")} onChange={(event) => setDraft({ ...draft, [key]: percentage ? Number(event.target.value) / 100 : Number(event.target.value) })} /></label>;
  return <Card className="rules-card"><div className="section-heading"><div><p className="eyebrow">筛选策略</p><h3>规则阈值</h3></div><Settings2 size={18} /></div><p className="muted">硬规则会先过滤低质商品，再进入 AI 推理。</p><div className="form-grid">{field("commission_min", "最低佣金", "%", "0.1", true)}{field("shop_rating_min", "最低店铺评分", "分", "0.1")}{field("return_rate_max", "最高退货率", "%", "0.1", true)}{field("estimated_sales_min", "最低预估销量", "件", "100")}{field("ai_score_min", "最低 AI 综合分", "分", "1")}</div><Button className="full" onClick={() => mutation.mutate(draft)} disabled={!canEdit || mutation.isPending}>{mutation.isPending ? <Spinner /> : <RefreshCw size={15} />}保存阈值</Button></Card>;
}

function ProductModal({ id, onClose }) {
  const { data, isLoading } = useQuery({ queryKey: ["product", id], queryFn: () => getProduct(id), enabled: Boolean(id) });
  const product = data?.data;
  return <Modal open={Boolean(id)} title={product?.title || "商品详情"} onClose={onClose}>{isLoading ? <div className="loading"><Spinner /></div> : product && <div className="detail"><img src={product.image_url} alt="" /><div className="detail-grid"><div><span>售价</span><strong>{money(product.price)}</strong></div><div><span>佣金比例</span><strong className="red-text">{pct(product.commission_rate)}</strong></div><div><span>预估销量</span><strong>{Number(product.estimated_sales).toLocaleString()}</strong></div><div><span>店铺评分</span><strong>{product.shop_rating.toFixed(1)}</strong></div><div><span>退货率</span><strong>{pct(product.return_rate)}</strong></div><div><span>销量增速</span><strong className="green-text">↗ {pct(product.sales_growth)}</strong></div></div><div className="detail-copy"><Badge tone="gray">{product.category}</Badge><p>{product.description}</p></div></div>}</Modal>;
}

function InsightModal({ insight, onClose }) {
  return <Modal open={Boolean(insight)} title={`${insight?.title || "商品"} · AI 解释`} onClose={onClose}>{insight && <div className="insight-detail"><div className="insight-score-grid"><div><span>综合分</span><strong>{insight.final_score}</strong></div><div><span>潜力分</span><strong>{insight.ai_score}</strong></div><div><span>语义分</span><strong>{insight.semantic_score}</strong></div><div><span>图文分</span><strong>{insight.multimodal_score}</strong></div></div><div className="detail-copy"><Badge tone="gray">{insight.content_topic}</Badge><p>{insight.ai_advice}</p><ul>{(insight.score_factors || []).map((factor) => <li key={factor}>{factor}</li>)}</ul><p className="model-note">图片理解：{insight.image_description}<br />模型来源：{Object.entries(insight.model_sources || {}).map(([key, value]) => `${key}=${value}`).join(" · ")}</p></div></div>}</Modal>;
}

function InferenceMeta({ trace }) {
  if (!trace) return null;
  return <div className="inference-meta"><div><span>推荐批次</span><strong>{trace.recommendation_id}</strong></div><div><span>推理耗时</span><strong>{trace.runtime?.inference_ms ?? "—"} ms</strong></div><div><span>清洗过滤</span><strong>{trace.cleaning_removed ?? 0} 条</strong></div><div><span>权重</span><strong>55 / 30 / 15</strong></div><div><span>模型链路</span><strong>{Object.values(trace.model_versions || {}).join(" · ")}</strong></div></div>;
}

function QualityStrip({ quality }) {
  if (!quality) return null;
  return <div className="quality-strip"><div><span>数据质量</span><strong>{pct(quality.quality_rate)}</strong></div><div><span>原始商品</span><strong>{quality.raw_count}</strong></div><div><span>刷单过滤</span><strong>{quality.fraud_suspect_count}</strong></div><div><span>重复 / 异常</span><strong>{quality.duplicate_count} / {quality.anomaly_count}</strong></div><div><span>清洗后候选</span><strong>{quality.cleaned_count}</strong></div><small>{quality.rule}</small></div>;
}

function ModelStrip({ models }) {
  if (!models?.length) return null;
  return <div className="model-strip"><div className="model-strip-head"><span>模型运行状态</span><small>只展示运行元数据，不暴露密钥</small></div><div className="model-list">{models.map((item) => <div className="model-item" key={item.role}><span className={`status-dot ${item.status === "active" ? "active" : "fallback"}`} /><div><strong>{item.role}</strong><small>{item.model} · {item.provider}</small></div><Badge tone={item.status === "active" ? "green" : "gray"}>{item.status === "active" ? "已启用" : "Demo 回退"}</Badge></div>)}</div></div>;
}

function DraftModal({ draftInput, onClose }) {
  const mutation = useMutation({ mutationFn: createContentDraft });
  useEffect(() => { if (draftInput) mutation.mutate(draftInput); else mutation.reset(); }, [draftInput]);
  const draft = mutation.data?.data;
  return <Modal open={Boolean(draftInput)} title={draft?.product_title ? `${draft.product_title} · 图文草稿` : "生成图文草稿"} onClose={onClose}>{mutation.isPending ? <div className="loading"><Spinner /><span>正在生成标题、首图文案和分镜…</span></div> : mutation.isError ? <div className="error">内容生成失败，请稍后重试。</div> : draft && <div className="draft-detail"><div className="draft-hero"><Badge tone="red">#{draft.hotspot_keyword}</Badge><h3>{draft.title}</h3><p>{draft.cover_copy}</p></div><div className="draft-section"><h4>图文分镜</h4>{draft.slides?.map((slide, index) => <div className="draft-slide" key={`${slide.image_direction}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{slide.image_direction}</strong><p>{slide.copy}</p></div></div>)}</div><div className="draft-columns"><div className="draft-section"><h4>核心卖点</h4><ul>{draft.selling_points?.map((item) => <li key={item}>{item}</li>)}</ul></div><div className="draft-section risk"><h4>风险提示</h4><ul>{draft.risk_notes?.map((item) => <li key={item}>{item}</li>)}</ul></div></div><small className="model-note">生成来源：{draft.model} · Prompt：{draft.prompt_version} · 质量检查：{draft.quality_checks?.slide_count || 0} 张分镜 · 草稿 ID：{draft.draft_id}</small></div>}</Modal>;
}

export default function WorkspacePage() {
  const { isAdmin, canOperate } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeId, setActiveId] = useState();
  const [activeInsight, setActiveInsight] = useState();
  const [draftInput, setDraftInput] = useState();
  const [notice, setNotice] = useState("");
  const { data: hotData, isLoading: hotLoading } = useQuery({ queryKey: ["hotspots"], queryFn: getHotspots });
  const { data: ruleData, isLoading: ruleLoading } = useQuery({ queryKey: ["rules"], queryFn: getRules });
  const { data: qualityData } = useQuery({ queryKey: ["data-quality"], queryFn: getDataQuality });
  const { data: modelsData } = useQuery({ queryKey: ["models"], queryFn: getModels });
  const recMutation = useMutation({ mutationFn: recommend, onSuccess: () => setNotice("AI 推理完成，榜单已更新") });
  const hotspots = hotData?.data || [];
  const requestedHotspot = searchParams.get("hotspot_id");
  const selected = hotspots.some((item) => item.hotspot_id === requestedHotspot) ? requestedHotspot : hotspots[0]?.hotspot_id;
  const currentHot = hotspots.find((item) => item.hotspot_id === selected);
  const rules = ruleData?.data || {};
  const quality = qualityData?.data;
  const models = modelsData?.data || [];
  const rows = recMutation.data?.data?.recommendations || [];
  const filtered = recMutation.data?.data?.filtered || [];
  const stats = useMemo(() => ({ candidates: recMutation.data?.data?.candidate_count ?? "—", passed: recMutation.data?.data?.passed_count ?? "—", avg: rows.length ? (rows.reduce((sum, row) => sum + row.final_score, 0) / rows.length).toFixed(1) : "—" }), [recMutation.data, rows]);
  const selectHotspot = (id) => setSearchParams({ hotspot_id: id });
  const runAI = () => { setNotice(""); recMutation.mutate({ hotspot_id: selected, limit: 10 }); };
  const openProduct = (row) => { setActiveId(row.product_id); setActiveInsight(undefined); };
  const openInsight = (row) => { setActiveId(undefined); setActiveInsight(row); };
  const goFeedback = (row) => navigate(`/feedback?product_id=${row.product_id}&hotspot_id=${selected || ""}&recommendation_id=${recMutation.data?.data?.recommendation_id || ""}`);
  const openDraft = (row) => setDraftInput({ product_id: row.product_id, hotspot_id: selected, recommendation_id: recMutation.data?.data?.recommendation_id });

  return <div className="content"><div className="overview"><div><p className="eyebrow">TODAY'S SIGNALS</p><h2>捕捉热点，找到下一件爆款</h2><p className="muted">规则预筛 + AI 语义匹配 + 图文潜力评分，给运营一个可解释的推荐榜单。</p></div><Button onClick={runAI} disabled={!canOperate || recMutation.isPending || hotLoading}>{recMutation.isPending ? <><Spinner /> AI 推理中</> : <><Sparkles size={16} />AI 一键选品</>}</Button></div><div className="stats"><Stat icon={Search} label="候选商品" value={stats.candidates} detail="清洗后可评估" /><Stat icon={Filter} label="通过筛选" value={stats.passed} detail="硬规则 + AI 阈值" tone="teal" /><Stat icon={Gauge} label="榜单平均分" value={stats.avg} detail="综合转化潜力" tone="amber" /><Stat icon={TrendingUp} label="热点上升" value={currentHot ? pct(currentHot.rise_rate) : "—"} detail="当前热点 24h" tone="purple" /></div><QualityStrip quality={quality} /><ModelStrip models={models} /><div className="workspace-grid"><Card className="hot-card"><div className="section-heading"><div><p className="eyebrow">REAL-TIME TOPICS</p><h3>热点看板</h3></div><Badge tone="green"><span className="live-dot" /> 实时模拟</Badge></div>{hotLoading ? <div className="loading"><Spinner /></div> : <HotspotList hotspots={hotspots} selected={selected} onSelect={selectHotspot} />}</Card><RulePanel rules={ruleLoading ? {} : rules} canEdit={isAdmin} onSaved={() => setNotice("规则已保存，下次点击将使用新阈值")} /></div><Card className="recommend-card"><div className="section-heading rec-heading"><div><p className="eyebrow">AI RECOMMENDATIONS</p><h3>推荐商品榜单 {currentHot && <span>· #{currentHot.keyword}</span>}</h3></div><div className="rec-actions">{notice && <span className="notice">{notice}</span>}{canOperate && <a className="export" href={exportUrl(selected)}><Download size={15} /> 导出 CSV</a>}</div></div>{recMutation.isPending ? <div className="loading table-loading"><Spinner /><span>正在完成潜力打分、热点匹配与图文选题生成…</span></div> : recMutation.isError ? <div className="error">接口暂时不可用，请确认 FastAPI 已启动后重试。</div> : <><RecommendationTable rows={rows} canOperate={canOperate} onOpen={openProduct} onInsight={openInsight} onDraft={openDraft} onFeedback={goFeedback} /><FilterSummary filtered={filtered} /></>}<InferenceMeta trace={recMutation.data?.data} /></Card><div className="loop-strip"><div className="loop-step done"><span>01</span><strong>观测热点</strong><small>趋势看板</small></div><ChevronRight size={15} /><div className="loop-step done"><span>02</span><strong>AI 选品</strong><small>规则 + 模型</small></div><ChevronRight size={15} /><div className="loop-step"><span>03</span><strong>投放回流</strong><small>曝光 · 点击 · 成交</small></div><ChevronRight size={15} /><div className="loop-step"><span>04</span><strong>模型迭代</strong><small>样本待训练</small></div></div><ProductModal id={activeId} onClose={() => setActiveId()} /><InsightModal insight={activeInsight} onClose={() => setActiveInsight()} /><DraftModal draftInput={draftInput} onClose={() => setDraftInput()} /></div>;
}
