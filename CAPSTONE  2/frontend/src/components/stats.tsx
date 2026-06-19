import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Activity,
	CalendarCheck,
	CalendarClock,
	CheckCircle2,
	ClipboardList,
	Stethoscope,
	Star,
	UserRound,
	Users,
	XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type Stat = {
	label: string;
	value: string | number | null;
	hint?: string;
};

/** Pick a representative icon purely from the existing label text — no new data needed. */
function iconForLabel(label: string): LucideIcon {
	const l = label.toLowerCase();
	if (l.includes("cancel")) return XCircle;
	if (l.includes("complet") || l.includes("past")) return CheckCircle2;
	if (l.includes("rating")) return Star;
	if (l.includes("today")) return CalendarCheck;
	if (l.includes("upcoming")) return CalendarClock;
	if (l.includes("doctor")) return Stethoscope;
	if (l.includes("secretar")) return UserRound;
	if (l.includes("patient")) return Users;
	if (l.includes("appointment")) return ClipboardList;
	return Activity;
}

export function DashboardStats({ stats }: { stats: Stat[] }) {
	return (
		<>
			{stats.map((s, i) => (
				<StatCard key={s.label} stat={s} delay={i * 60} />
			))}
		</>
	);
}

function StatCard({ stat, delay }: { stat: Stat; delay: number }) {
	const { label, value, hint } = stat;
	const Icon = iconForLabel(label);
	return (
		<Card
			className="animate-fade-up gap-0 border-border/70 pb-0 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-[#4382DF]/10"
			style={{ animationDelay: `${delay}ms` }}
		>
			<CardHeader className="flex flex-row items-start justify-between gap-3 border-b pb-3">
				<div className="flex min-w-0 flex-col gap-1">
					<CardTitle className="font-mono text-3xl text-[#112E81] tabular-nums tracking-tight">
						{value ?? "—"}
					</CardTitle>
					<CardDescription className="font-medium text-xs uppercase tracking-wide">
						{label}
					</CardDescription>
				</div>
				<span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-[#112E81]">
					<Icon aria-hidden="true" className="size-4.5" />
				</span>
			</CardHeader>
			<CardContent className="py-3 text-xs">
				<span className="text-pretty text-muted-foreground">{hint ?? " "}</span>
			</CardContent>
		</Card>
	);
}
