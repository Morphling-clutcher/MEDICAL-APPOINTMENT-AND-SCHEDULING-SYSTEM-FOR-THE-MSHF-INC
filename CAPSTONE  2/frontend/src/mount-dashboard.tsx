import { createRoot } from "react-dom/client";
import { Dashboard, type DashboardData } from "@/components/dashboard";
import "@/index.css";

export function mountDashboard(role: string) {
	const dataEl = document.getElementById("dashboard-data");
	const root = document.getElementById("react-dashboard-root");
	if (!dataEl || !root) return;

	const data = JSON.parse(dataEl.textContent || "{}") as DashboardData;
	root.setAttribute("data-role", role);
	createRoot(root).render(<Dashboard data={data} />);
}
