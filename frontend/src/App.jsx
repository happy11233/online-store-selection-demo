import React, { useEffect, useState } from "react";
import { Activity, Bot, DatabaseZap, LayoutDashboard, LogOut, TrendingUp, Users } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthContext } from "./auth-context";
import { Badge, Spinner } from "./components/ui";
import { getMe, logout, setCsrfToken } from "./lib/api";
import FeedbackPage from "./pages/FeedbackPage";
import HotspotsPage from "./pages/HotspotsPage";
import LoginPage from "./pages/LoginPage";
import SourcesPage from "./pages/SourcesPage";
import UsersPage from "./pages/UsersPage";
import WorkspacePage from "./pages/WorkspacePage";

const pages = {
  "/workspace": "智能选品工作台", "/hotspots": "热点趋势", "/feedback": "投放回流",
  "/sources": "数据源接入", "/users": "账号与权限",
};
const roles = { admin: "管理员", operator: "运营", viewer: "观察员" };

function ShellHeader({ user, onLogout }) {
  const location = useLocation();
  const title = pages[location.pathname] || pages["/workspace"];
  return <header className="topbar"><div><span className="crumb">业务中心 / {title}</span><h1>{title}</h1></div><div className="top-actions"><span className="sync"><span className="live-dot" />本地演示 · 模拟数据</span><span className="user-pill">{user.username} <Badge tone="gray">{roles[user.role]}</Badge></span><button className="logout-button" onClick={onLogout} aria-label="退出登录"><LogOut size={15} />退出</button></div></header>;
}

function Sidebar({ isAdmin }) {
  return <aside className="sidebar"><div className="brand"><div className="brand-mark"><Bot size={20} /></div><div><strong>AIMID</strong><span>内容商业智能</span></div></div><nav><NavLink to="/workspace" className="nav-item"><LayoutDashboard size={17} />选品工作台</NavLink><NavLink to="/hotspots" className="nav-item"><TrendingUp size={17} />热点趋势</NavLink><NavLink to="/feedback" className="nav-item"><Activity size={17} />投放回流</NavLink><NavLink to="/sources" className="nav-item"><DatabaseZap size={17} />数据源接入</NavLink>{isAdmin && <NavLink to="/users" className="nav-item"><Users size={17} />账号与权限</NavLink>}</nav><div className="side-bottom"><div className="mode"><span className="live-dot" />Demo 环境 <Badge tone="gray">离线数据</Badge></div><p>AI 开发工程师演示项目<br />FastAPI · Qwen · React</p></div></aside>;
}

export default function App() {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    getMe().then((result) => { if (live) { setCsrfToken(result.data.csrf_token); setUser(result.data); } }).catch(() => {}).finally(() => { if (live) setLoading(false); });
    const unauthorized = () => { setCsrfToken(""); setUser(null); queryClient.clear(); };
    window.addEventListener("aimid:unauthorized", unauthorized);
    return () => { live = false; window.removeEventListener("aimid:unauthorized", unauthorized); };
  }, [queryClient]);
  const authenticated = (session) => { setCsrfToken(session.csrf_token); setUser(session); queryClient.clear(); };
  const signOut = async () => { try { await logout(); } finally { setCsrfToken(""); setUser(null); queryClient.clear(); } };
  if (loading) return <div className="app-loading"><Spinner /><span>正在检查登录状态…</span></div>;
  if (!user) return <LoginPage onAuthenticated={authenticated} />;
  return <AuthContext.Provider value={{ user }}><div className="app-shell"><Sidebar isAdmin={user.role === "admin"} /><main className="main"><ShellHeader user={user} onLogout={signOut} /><Routes><Route path="/" element={<Navigate to="/workspace" replace />} /><Route path="/workspace" element={<WorkspacePage />} /><Route path="/hotspots" element={<HotspotsPage />} /><Route path="/feedback" element={<FeedbackPage />} /><Route path="/sources" element={<SourcesPage />} /><Route path="/users" element={user.role === "admin" ? <UsersPage /> : <Navigate to="/workspace" replace />} /><Route path="*" element={<Navigate to="/workspace" replace />} /></Routes></main></div></AuthContext.Provider>;
}
