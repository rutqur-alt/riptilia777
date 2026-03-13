/**
 * Shared sidebar badge component used by TraderDashboard and MerchantDashboard.
 * Displays a red notification count badge next to sidebar menu items.
 */
export default function SidebarBadge({ count }) {
  if (!count || count === 0) return null;
  return (
    <span className="ml-auto bg-[#EF4444] text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
      {count > 99 ? "99+" : count}
    </span>
  );
}
