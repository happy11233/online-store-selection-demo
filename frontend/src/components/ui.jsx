import React from "react";

export function Button({ children, variant = "primary", className = "", ...props }) {
  return <button className={`btn btn-${variant} ${className}`} {...props}>{children}</button>;
}

export function Card({ children, className = "" }) { return <section className={`card ${className}`}>{children}</section>; }
export function Badge({ children, tone = "gray" }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
export function Modal({ open, title, onClose, children }) {
  if (!open) return null;
  return <div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal"><div className="modal-head"><div><p className="eyebrow">商品洞察</p><h2>{title}</h2></div><button className="icon-btn" onClick={onClose} aria-label="关闭">×</button></div>{children}</div></div>;
}
export function Spinner() { return <span className="spinner" aria-label="加载中" />; }
