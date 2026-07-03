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
import { ChevronRightIcon, ZapIcon } from "lucide-react";

export type QuickAction = {
	title: string;
	description?: string;
	href: string;
};

export function QuickActions({ actions }: { actions: QuickAction[] }) {
	return (
		<Card className="animate-fade-up border-border/70" style={{ animationDelay: "320ms" }}>
			<CardHeader>
				<CardTitle className="text-[#16404C]">Quick actions</CardTitle>
				<CardDescription>Shortcuts to common tasks.</CardDescription>
			</CardHeader>
			<CardContent>
				<ItemGroup className="gap-1">
					{actions.map((a) => (
						<Item asChild key={a.title} size="sm">
							<a
								className="group rounded-xl transition-all duration-200 hover:translate-x-0.5 hover:bg-accent"
								href={a.href}
							>
								<ItemMedia variant="icon" className="bg-accent text-[#16404C] transition-colors group-hover:bg-[#2AAFC4] group-hover:text-white">
									<ZapIcon aria-hidden="true" />
								</ItemMedia>
								<ItemContent>
									<ItemTitle className="group-hover:text-[#16404C]">{a.title}</ItemTitle>
									{a.description ? (
										<ItemDescription className="line-clamp-1">
											{a.description}
										</ItemDescription>
									) : null}
								</ItemContent>
								<ItemActions>
									<ChevronRightIcon
										aria-hidden="true"
										className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-[#2AAFC4]"
									/>
								</ItemActions>
							</a>
						</Item>
					))}
				</ItemGroup>
			</CardContent>
		</Card>
	);
}
