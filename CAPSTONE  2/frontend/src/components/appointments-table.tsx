import { ArrowRightIcon } from "lucide-react";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Table,
	TableBody,
	TableCaption,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/components/formater";

export type AppointmentRow = {
	primary: string;
	secondary?: string;
	date: string;
	time?: string;
	status: string;
};

/* Design-system status badges — soft tint + text color per spec:
 * Pending=amber · Approved/Scheduled=green · Completed=blue ·
 * Rescheduled=purple · Cancelled=gray. Each is paired with a circular
 * status dot (rendered alongside the label below). */
const statusStyles: Record<string, string> = {
	"Pending Time Assignment": "border-transparent bg-amber-100 text-amber-700 hover:bg-amber-200/80",
	Scheduled: "border-transparent bg-green-100 text-green-700 hover:bg-green-200/70",
	Rescheduled: "border-transparent bg-violet-100 text-violet-700 hover:bg-violet-200/70",
	Completed: "border-transparent bg-blue-100 text-blue-700 hover:bg-blue-200/70",
	Cancelled: "border-transparent bg-gray-100 text-gray-600 hover:bg-gray-200/70",
};

const avatarPalette = ["#2AAFC4", "#17758B", "#2697B3", "#52C2D5"];

function initials(name: string) {
	const parts = name.trim().split(/\s+/);
	const first = parts[0]?.[0] ?? "";
	const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? "" : "";
	return (first + last).toUpperCase() || "?";
}

export function AppointmentsTable({
	title,
	rows,
	emptyMessage = "No appointments yet.",
	viewAllHref,
}: {
	title: string;
	rows: AppointmentRow[];
	emptyMessage?: string;
	viewAllHref?: string;
}) {
	const hasSecondary = rows.some((r) => r.secondary);
	const showViewAll = Boolean(viewAllHref) && rows.length > 0;
	return (
		<Card className="animate-fade-up border-border/70 md:col-span-2" style={{ animationDelay: "260ms" }}>
			<CardHeader>
				<CardTitle className="text-balance text-[#16404C]">{title}</CardTitle>
				<CardDescription className="text-pretty">
					{rows.length} {rows.length === 1 ? "appointment" : "appointments"}
				</CardDescription>
			</CardHeader>
			<CardContent className="p-0 pb-2">
				{rows.length === 0 ? (
					<p className="py-8 text-center text-muted-foreground">{emptyMessage}</p>
				) : (
					<Table className="border-t">
						<TableCaption className="sr-only">
							{title}, with patient or doctor, date, and status.
						</TableCaption>
						<TableHeader>
							<TableRow>
								<TableHead className="pl-6" scope="col">
									Name
								</TableHead>
								{hasSecondary ? <TableHead scope="col">Detail</TableHead> : null}
								<TableHead scope="col">Date</TableHead>
								<TableHead className="pr-6 text-end" scope="col">
									Status
								</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{rows.map((r, i) => (
								<TableRow className="hover:bg-accent/40" key={i}>
									<TableCell className="pl-6 font-medium">
										<div className="flex items-center gap-3">
											<span
												className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
												style={{ backgroundColor: avatarPalette[i % avatarPalette.length] }}
											>
												{initials(r.primary)}
											</span>
											{r.primary}
										</div>
									</TableCell>
									{hasSecondary ? (
										<TableCell className="text-muted-foreground">{r.secondary}</TableCell>
									) : null}
									<TableCell className="text-muted-foreground text-xs tabular-nums">
										{formatDate(r.date, "day-month")}
										{r.time ? ` · ${r.time}` : ""}
									</TableCell>
									<TableCell className="pr-6 text-end">
										<Badge className={statusStyles[r.status] ?? "border-border text-foreground"}>
											{r.status}
										</Badge>
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				)}
			</CardContent>

			{showViewAll ? (
				<div className="flex justify-center border-t pt-2">
					<Button asChild variant="ghost">
						<a href={viewAllHref}>
							View All
							<ArrowRightIcon aria-hidden="true" className="size-4" />
						</a>
					</Button>
				</div>
			) : null}
		</Card>
	);
}
