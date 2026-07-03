import {
	Stethoscope,
	HeartPulse,
	Brain,
	Baby,
	Bone,
	Pill,
	Syringe,
	Activity,
	Eye,
	Smile,
} from "lucide-react";
import type { CategoryItem } from "@/types";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
	stethoscope: Stethoscope,
	heart: HeartPulse,
	brain: Brain,
	baby: Baby,
	bone: Bone,
	pill: Pill,
	syringe: Syringe,
	activity: Activity,
	eye: Eye,
	smile: Smile,
};

const PALETTE = [
	"bg-[#FBE4E4] text-[#C24545]",
	"bg-[#E1F0E6] text-[#2F8F5B]",
	"bg-[#FCE8D6] text-[#C8762B]",
	"bg-[#E9E5F7] text-[#6750A4]",
	"bg-[#DCEFEC] text-[#2C7A72]",
	"bg-[#E4E1F0] text-[#4B3F8F]",
	"bg-[#F6E1E8] text-[#A8447B]",
	"bg-[#DCEAFB] text-[#3568B5]",
];

export function Categories({
	items,
	href,
}: {
	items: CategoryItem[];
	href?: string;
}) {
	if (!items || items.length === 0) return null;

	return (
		<div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
			<div className="flex items-center justify-between mb-3">
				<h2 className="font-semibold text-base text-[#1F2937]">Categories</h2>
				{href && (
					<a href={href} className="text-sm text-[#2AAFC4] hover:underline">
						See All
					</a>
				)}
			</div>
			<div className="grid grid-cols-4 gap-3">
				{items.map((item, i) => {
					const Icon = ICONS[iconKeyFor(item.name)] ?? Stethoscope;
					const colorClass = PALETTE[i % PALETTE.length];
					return (
						<a
							key={item.name}
							href={item.href}
							className="flex flex-col items-center gap-1.5 group"
						>
							<span
								className={`flex size-14 items-center justify-center rounded-2xl transition-transform group-hover:scale-105 ${colorClass}`}
							>
								<Icon className="size-6" />
							</span>
							<span className="text-xs text-center text-[#4B5563] leading-tight line-clamp-2">
								{item.name}
							</span>
						</a>
					);
				})}
			</div>
		</div>
	);
}

function iconKeyFor(name: string): string {
	const n = name.toLowerCase();
	if (n.includes("cardio") || n.includes("heart")) return "heart";
	if (n.includes("neuro") || n.includes("brain")) return "brain";
	if (n.includes("pedia") || n.includes("child")) return "baby";
	if (n.includes("ortho") || n.includes("bone")) return "bone";
	if (n.includes("dent") || n.includes("tooth")) return "smile";
	if (n.includes("eye") || n.includes("ophthal")) return "eye";
	if (n.includes("pharma") || n.includes("medicine")) return "pill";
	if (n.includes("vaccin") || n.includes("immuni")) return "syringe";
	if (n.includes("general") || n.includes("family")) return "activity";
	return "stethoscope";
}
