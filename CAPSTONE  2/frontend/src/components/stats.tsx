import { cn } from "@/lib/utils";
import type React from "react";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import type { DashboardStat } from "@/types";

export function DashboardStats({ stats }: { stats: DashboardStat[] }) {
	return (
		<>
			{stats.map((s, i) => (
				<StatCard key={s.label} stat={s} style={{ animationDelay: `${i * 60}ms` }} />
			))}
		</>
	);
}

function StatCard({
	stat,
	className,
	...props
}: React.ComponentProps<typeof Card> & { stat: DashboardStat }) {
	const { label, value, hint } = stat;
	const displayValue = value ?? "—";
	return (
		<Card
			className={cn("animate-fade-up border-border/70", className)}
			{...props}
		>
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle className="font-normal text-muted-foreground text-xs tracking-wide">
					{label}
				</CardTitle>
				{hint && (
					<CardDescription className="text-xs tabular-nums">
						{hint}
					</CardDescription>
				)}
			</CardHeader>
			<CardContent className="flex flex-row items-center gap-2">
				<p className="font-semibold text-2xl tabular-nums text-[#16404C]">{displayValue}</p>
			</CardContent>
		</Card>
	);
}
