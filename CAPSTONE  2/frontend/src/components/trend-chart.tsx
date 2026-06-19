import { useId } from "react";
import { TrendingDownIcon, TrendingUpIcon } from "lucide-react";
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts";
import { formatChartAxisTick, formatChartTooltipDate, formatInteger } from "@/components/formater";
import { Badge } from "@/components/ui/badge";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	type ChartConfig,
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
} from "@/components/ui/chart";

/** Trailing half vs leading half of the period — the only "vs prior" comparison the data actually supports. */
function trendDeltaPercent(data: TrendPoint[]): number | null {
	if (data.length < 2) return null;
	const mid = Math.floor(data.length / 2);
	const leading = data.slice(0, mid).reduce((sum, p) => sum + p.value, 0);
	const trailing = data.slice(mid).reduce((sum, p) => sum + p.value, 0);
	if (leading === 0) return trailing === 0 ? null : 100;
	return ((trailing - leading) / leading) * 100;
}

export type TrendPoint = { date: string; value: number };

export function TrendChart({
	title,
	data,
	valueLabel,
}: {
	title: string;
	data: TrendPoint[];
	valueLabel: string;
}) {
	const chartUid = useId().replace(/:/g, "");
	const idAreaGradient = `trend-area-grad-${chartUid}`;
	const periodDays = data.length;
	const total = data.reduce((sum, point) => sum + point.value, 0);
	const deltaPercent = trendDeltaPercent(data);

	const chartConfig = {
		value: { label: valueLabel, color: "var(--chart-1)" },
	} satisfies ChartConfig;

	return (
		<Card className="animate-fade-up border-border/70 md:col-span-2 lg:col-span-3" style={{ animationDelay: "200ms" }}>
			<CardHeader className="flex flex-row items-start justify-between">
				<div className="flex flex-col gap-1.5">
					<CardTitle className="font-mono text-2xl text-[#112E81] tabular-nums">
						{formatInteger(total)}
					</CardTitle>
					<CardDescription className="text-balance text-pretty">{title}</CardDescription>
				</div>
				{deltaPercent !== null ? (
					<Badge
						className="gap-1 border-none tabular-nums [&_svg]:size-3.5 [&_svg]:shrink-0"
						variant="secondary"
					>
						{deltaPercent >= 0 ? <TrendingUpIcon aria-hidden="true" /> : <TrendingDownIcon aria-hidden="true" />}
						<span>
							{deltaPercent >= 0 ? "+" : ""}
							{deltaPercent.toFixed(1)}%
						</span>
						<span className="hidden sm:inline">vs first half</span>
					</Badge>
				) : null}
			</CardHeader>
			<CardContent>
				<ChartContainer className="aspect-auto h-60 w-full p-0" config={chartConfig}>
					<AreaChart accessibilityLayer data={[...data]} margin={{ left: 24, right: 8, top: 8, bottom: 0 }}>
						<defs>
							<linearGradient id={idAreaGradient} x1="0" x2="0" y1="0" y2="1">
								<stop offset="0%" stopColor="var(--color-value)" stopOpacity={0.2} />
								<stop offset="100%" stopColor="var(--color-value)" stopOpacity={0} />
							</linearGradient>
						</defs>
						<CartesianGrid horizontal={false} strokeDasharray="2 2" />
						<XAxis
							axisLine={false}
							dataKey="date"
							tickFormatter={(value) => formatChartAxisTick(String(value), periodDays)}
							tickLine={false}
							tickMargin={8}
						/>
						<ChartTooltip
							content={
								<ChartTooltipContent
									className="min-w-36"
									indicator="line"
									labelFormatter={(_, payload) => {
										const row = payload?.[0]?.payload as TrendPoint | undefined;
										if (!row?.date) return "";
										return formatChartTooltipDate(row.date, "short");
									}}
								/>
							}
						/>
						<Area
							dataKey="value"
							dot={false}
							fill={`url(#${idAreaGradient})`}
							stroke="var(--color-value)"
							strokeWidth={2}
							type="monotone"
						/>
					</AreaChart>
				</ChartContainer>
			</CardContent>
		</Card>
	);
}
