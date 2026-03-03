/**
 * Shared UI components for Admin Panel
 */
import React from "react";

// Stat Card - displays a metric with icon and optional subtitle
export function StatCard({ title, value, sub, icon: Icon, color = "green", onClick }) {
  const colors = {
    green: "from-[#10B981]/20 to-[#10B981]/5 border-[#10B981]/20",
    red: "from-[#EF4444]/20 to-[#EF4444]/5 border-[#EF4444]/20",
    yellow: "from-[#F59E0B]/20 to-[#F59E0B]/5 border-[#F59E0B]/20",
    purple: "from-[#7C3AED]/20 to-[#7C3AED]/5 border-[#7C3AED]/20",
    blue: "from-[#3B82F6]/20 to-[#3B82F6]/5 border-[#3B82F6]/20"
  };
  const iconColors = {
    green: "text-[#10B981]",
    red: "text-[#EF4444]",
    yellow: "text-[#F59E0B]",
    purple: "text-[#A78BFA]",
    blue: "text-[#60A5FA]"
  };
  return (
    <div 
      onClick={onClick}
      className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-4 ${onClick ? 'cursor-pointer hover:scale-[1.02] transition-transform' : ''}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-2xl font-bold text-white">{value}</div>
          <div className="text-xs text-[#A1A1AA] mt-0.5">{title}</div>
          {sub && <div className="text-[10px] text-[#52525B] mt-1">{sub}</div>}
        </div>
        <Icon className={`w-5 h-5 ${iconColors[color]}`} />
      </div>
    </div>
  );
}

// Badge - small label for status indicators
export function Badge({ children, color = "gray" }) {
  const colors = {
    green: "bg-[#10B981]/10 text-[#10B981]",
    red: "bg-[#EF4444]/10 text-[#EF4444]",
    yellow: "bg-[#F59E0B]/10 text-[#F59E0B]",
    purple: "bg-[#7C3AED]/10 text-[#A78BFA]",
    blue: "bg-[#3B82F6]/10 text-[#60A5FA]",
    gray: "bg-[#52525B]/20 text-[#A1A1AA]"
  };
  return (
    <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${colors[color]}`}>
      {children}
    </span>
  );
}

// Loading Spinner
export function LoadingSpinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-6 h-6 border-2 border-[#10B981] border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// Empty State - shown when no data
export function EmptyState({ icon: Icon, text }) {
  return (
    <div className="bg-[#121212] border border-white/5 rounded-xl p-12 text-center">
      <Icon className="w-10 h-10 text-[#3F3F46] mx-auto mb-3" />
      <p className="text-[#71717A] text-sm">{text}</p>
    </div>
  );
}

// Page Header with title, subtitle and action button
export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h1 className="text-xl font-bold text-white">{title}</h1>
        {subtitle && <p className="text-[#71717A] text-xs mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// Section Container
export function Section({ children, className = "" }) {
  return (
    <div className={`bg-[#121212] border border-white/5 rounded-xl p-4 ${className}`}>
      {children}
    </div>
  );
}

// Tab Button
export function TabButton({ active, onClick, children, badge }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
        active 
          ? "bg-white/10 text-white" 
          : "text-[#71717A] hover:text-white hover:bg-white/5"
      }`}
    >
      {children}
      {badge > 0 && (
        <span className="ml-1.5 px-1.5 py-0.5 text-[10px] bg-[#EF4444]/20 text-[#EF4444] rounded-full">
          {badge}
        </span>
      )}
    </button>
  );
}

// Action Button
export function ActionButton({ onClick, children, variant = "primary", size = "sm", disabled = false }) {
  const variants = {
    primary: "bg-[#10B981] hover:bg-[#059669] text-white",
    danger: "bg-[#EF4444] hover:bg-[#DC2626] text-white",
    secondary: "bg-white/10 hover:bg-white/20 text-white",
    ghost: "hover:bg-white/5 text-[#A1A1AA] hover:text-white"
  };
  const sizes = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-base"
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg font-medium transition-colors ${variants[variant]} ${sizes[size]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </button>
  );
}
