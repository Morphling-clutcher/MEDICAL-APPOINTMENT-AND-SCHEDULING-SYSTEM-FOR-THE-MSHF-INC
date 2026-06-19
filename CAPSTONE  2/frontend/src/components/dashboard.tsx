import { DashboardStats, type Stat } from "@/components/stats";
import { QuickActions, type QuickAction } from "@/components/quick-actions";
import { TrendChart, type TrendPoint } from "@/components/trend-chart";
import { AppointmentsTable, type AppointmentRow } from "@/components/appointments-table";

export type DashboardData = {
	stats: Stat[];
	trend?: TrendPoint[];
	trendLabel?: string;
	appointmentsTitle?: string;
	appointments?: AppointmentRow[];
	appointmentsHref?: string;
	pastAppointmentsTitle?: string;
	pastAppointments?: AppointmentRow[];
	pastAppointmentsHref?: string;
	quickActions: QuickAction[];
};

export function Dashboard({ data }: { data: DashboardData }) {
	return (
		<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4 lg:grid-flow-row-dense">
			{data.trend && data.trend.length > 0 ? (
				<TrendChart data={data.trend} title={data.trendLabel ?? "Trend"} valueLabel={data.trendLabel ?? "Value"} />
			) : null}
			<DashboardStats stats={data.stats} />
			{data.appointments ? (
				<AppointmentsTable
					rows={data.appointments}
					title={data.appointmentsTitle ?? "Appointments"}
					viewAllHref={data.appointmentsHref}
				/>
			) : null}
			{data.pastAppointments ? (
				<AppointmentsTable
					rows={data.pastAppointments}
					title={data.pastAppointmentsTitle ?? "Past Appointments"}
					viewAllHref={data.pastAppointmentsHref}
				/>
			) : null}
			<QuickActions actions={data.quickActions} />
		</div>
	);
}
