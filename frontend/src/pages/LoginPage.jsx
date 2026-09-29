import React, { useEffect, useState } from "react";
import { Bot, LockKeyhole, ShieldCheck } from "lucide-react";
import { Button, Spinner } from "../components/ui";
import { bootstrap, getAuthStatus, login } from "../lib/api";

export default function LoginPage({ onAuthenticated }) {
  const [initialized, setInitialized] = useState(null);
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  useEffect(() => { getAuthStatus().then((result) => setInitialized(result.data.initialized)).catch(() => setError("无法读取服务状态，请确认后端已启动。")); }, []);
  const submit = async (event) => {
    event.preventDefault(); setError(""); setPending(true);
    try {
      const result = await (initialized ? login(form) : bootstrap(form));
      onAuthenticated(result.data);
    } catch (failure) {
      setError(failure.response?.data?.detail || "登录失败，请检查服务状态。");
      if (failure.response?.status === 409) setInitialized(true);
    } finally { setPending(false); }
  };
  return <div className="login-page"><div className="login-feature"><div className="login-brand"><span className="brand-mark"><Bot size={21} /></span><strong>AIMID</strong></div><div><span className="login-kicker">AI CONTENT COMMERCE</span><h1>从热点到商品，<br />每一步都可解释。</h1><p>本地演示工作台 · 模拟数据 · 商品推荐与投放回流闭环</p></div><div className="login-foot">系统登录与抖音平台授权分别管理</div></div><div className="login-panel"><div className="login-card"><div className="login-icon"><ShieldCheck size={25} /></div><p className="eyebrow">SECURE WORKSPACE</p><h2>{initialized === false ? "首次设置管理员" : "登录工作台"}</h2><p className="muted">{initialized === false ? "创建本机管理员账号。密码至少 12 位。" : "使用系统账号访问工作台，不需要抖音平台凭证。"}</p><form onSubmit={submit}><label className="form-field"><span>用户名</span><input autoComplete="username" minLength={3} maxLength={40} required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} placeholder="请输入用户名" /></label><label className="form-field"><span>密码</span><input type="password" autoComplete={initialized === false ? "new-password" : "current-password"} minLength={12} required value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="至少 12 位" /></label>{error && <p className="form-error" role="alert">{error}</p>}<Button className="full" type="submit" disabled={pending || initialized === null}>{pending ? <Spinner /> : <LockKeyhole size={16} />}{initialized === false ? "创建并进入" : "登录"}</Button></form><small>本地 Demo 会话有效期 8 小时 · 账号信息仅在本机保存</small></div></div></div>;
}
