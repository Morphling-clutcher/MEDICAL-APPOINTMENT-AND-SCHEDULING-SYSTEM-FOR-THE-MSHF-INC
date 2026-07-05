"use client";

import { Badge } from "@/components/ui/badge";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Item,
	ItemActions,
	ItemContent,
	ItemDescription,
	ItemGroup,
	ItemMedia,
	ItemTitle,
} from "@/components/ui/item";
import { formatDate } from "@/components/formater";
import type { AppointmentRow } from "@/types";

/* Design-system status badges — soft tint + text color per spec:
 * Pending=amber · Approved/Scheduled=green · Completed=blue ·
 * Rescheduled=purple · Cancelled=gray. Each is paired with a circular
 * status dot (rendered alongside the label below). */
const statusStyles: Record<string, string> = {
	"Pending Assignment":
		"border-transparent bg-amber-100 text-amber-700 hover:bg-amber-200/80",
	Scheduled: "border-transparent bg-green-100 text-green-700 hover:bg-green-200/70",
	Confirmed:
		"border-transparent bg-teal-100 text-teal-700 hover:bg-teal-200/70",
	Rescheduled:
		"border-transparent bg-violet-100 text-violet-700 hover:bg-violet-200/70",
	"Pending Reschedule":
		"border-transparent bg-violet-100 text-violet-700 hover:bg-violet-200/70",
	Completed:
		"border-transparent bg-blue-100 text-blue-700 hover:bg-blue-200/70",
	Cancelled:
		"border-transparent bg-gray-100 text-gray-600 hover:bg-gray-200/70",
};

const avatarPalette = ["#2AAFC4", "#17758B", "#2697B3", "#52C2D5"];

function initials(name: string) {
	const parts = name.trim().split(/\s+/);
	const first = parts[0]?.[0] ?? "";
	const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? "" : "";
	return (first + last).toUpperCase() || "?";
}

export function DashboardAppointments({
	title,
	rows,
	href,
}: {
	title: string;
	rows: AppointmentRow[];
	href?: string;
}) {
	return (
		<Card className="animate-fade-up border-border/70">
			<CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
				<div className="flex flex-col space-y-1.5">
					<CardTitle className="text-[#16404C]">{title}</CardTitle>
					<CardDescription>
						{rows.length} {rows.length === 1 ? "appointment" : "appointments"}
					</CardDescription>
				</div>
				{href && rows.length > 0 && (
					<a
						href={href}
						className="text-sm font-medium text-[#2AAFC4] hover:underline"
					>
						View all
					</a>
				)}
			</CardHeader>
			<CardContent>
				{rows.length === 0 ? (
					<p className="py-8 text-center text-muted-foreground">
						No appointments.
					</p>
				) : (
					<ItemGroup className="gap-1">
						{rows.map((r, i) => (
							<Item key={i} size="sm" className="rounded-xl hover:bg-accent">
								<ItemMedia
									className="size-8 shrink-0 items-center justify-center rounded-full border-0 text-xs font-semibold text-white"
									style={{
										backgroundColor: avatarPalette[i % avatarPalette.length],
									}}
								>
									{initials(r.primary)}
								</ItemMedia>
								<ItemContent>
									<ItemTitle>{r.primary}</ItemTitle>
									<ItemDescription className="line-clamp-1">
										{r.secondary ? `${r.secondary} · ` : ""}
										{formatDate(r.date, "day-month")}
										{r.time ? ` · ${r.time}` : ""}
									</ItemDescription>
								</ItemContent>
								<ItemActions>
									<Badge
										className={
											statusStyles[r.status] ?? "border-border text-foreground"
										}
									>
										{r.status === "Pending Reschedule" && (
											<span className="relative mr-1.5 flex size-1.5">
												<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-violet-400 opacity-75" />
												<span className="relative inline-flex size-1.5 rounded-full bg-violet-500" />
											</span>
										)}
										{r.status !== "Pending Reschedule" && (
											<span className="mr-1.5 inline-flex size-1.5 rounded-full bg-current opacity-60" />
										)}
										{r.status}
									</Badge>
								</ItemActions>
							</Item>
						))}
					</ItemGroup>
				)}
			</CardContent>
		</Card>
	);
}
