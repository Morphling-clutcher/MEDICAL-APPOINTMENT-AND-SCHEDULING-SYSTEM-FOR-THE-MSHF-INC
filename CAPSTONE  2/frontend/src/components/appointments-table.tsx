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

/* Brand-aligned status colors. Cancelled stays red — the one place we keep a
 * non-brand color on purpose, so a cancellation still reads as "different"
 * at a glance rather than blending in with normal blue/indigo states. */
const statusStyles: Record<string, string> = {
	Scheduled: "border-transparent bg-[#4382DF] text-white hover:bg-[#4382DF]/90",
	Rescheduled: "border-transparent bg-[#4647AE] text-white hover:bg-[#4647AE]/90",
	Completed: "border-transparent bg-[#AACCD6]/40 text-[#112E81] hover:bg-[#AACCD6]/55",
	Cancelled: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/90",
};

const avatarPalette = ["#4382DF", "#4647AE", "#112E81", "#6B9FE0"];

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
				<CardTitle className="text-balance text-[#112E81]">{title}</CardTitle>
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
