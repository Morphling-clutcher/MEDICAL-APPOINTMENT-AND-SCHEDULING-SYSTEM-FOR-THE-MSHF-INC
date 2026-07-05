import { useState } from "react";
import {
	Search,
	Heart,
	ArrowRight,
	Stethoscope,
	HeartPulse,
	Brain,
	Baby,
	Bone,
	Eye,
	Smile,
	Syringe,
	Activity,
} from "lucide-react";
import { usePollingData } from "@/hooks/use-polling-data";
import { PromoCarousel } from "@/components/promo-carousel";
import type { DashboardData, DoctorCard, CategoryItem } from "@/types";

/* ────────────────────────────────────────────────────────────────────────
   Patient home — ported from the "DesignbyAwais" mobile mockup.
   Section order matches the design exactly:
   header → search → promo carousel → Browse by Specialty → Featured
   Doctors → Upcoming Appointment. Ratings were intentionally left out
   (no patient-visible ratings exist in this system); the ♡ button is a
   local-only toggle. The header has no avatar or bell — both already
   live in the site header / bottom nav, so this just shows the greeting
   text. ────────────────────────────────────────────────────────────── */

function WelcomeHeader({
	greeting,
	name,
}: {
	greeting: string;
	name?: string;
}) {
	return (
		<div className="min-w-0">
			<p className="text-sm text-[#6B7280] leading-tight">{greeting},</p>
			<h1 className="font-bold text-xl md:text-2xl text-[#1F2937] leading-tight truncate">
				{name}{" "}
				<span aria-hidden="true" className="align-middle">
					👋
				</span>
			</h1>
		</div>
	);
}

/* ── Search bar ─────────────────────────────────────────────────────────── */

function SearchBar({ baseHref }: { baseHref: string }) {
	const [query, setQuery] = useState("");
	const go = () => {
		const url = query.trim()
			? `${baseHref}?q=${encodeURIComponent(query.trim())}`
			: baseHref;
		window.location.href = url;
	};

	return (
		<div className="flex items-center gap-2.5 bg-white border border-[#E5E7EB] rounded-full px-3.5 py-2 shadow-sm">
			<Search className="size-4 text-[#9CA3AF] shrink-0" />
			<input
				type="text"
				value={query}
				onChange={(e) => setQuery(e.target.value)}
				onKeyDown={(e) => {
					if (e.key === "Enter") go();
				}}
				placeholder="Search doctors, specialties..."
				className="flex-1 min-w-0 bg-transparent border-0 p-0 text-sm text-[#1F2937] placeholder-[#9CA3AF] focus:outline-none focus:ring-0"
			/>
		</div>
	);
}

/* ── Browse by Specialty chips ─────────────────────────────────────────── */

const SPECIALTY_ICONS: [RegExp, React.ComponentType<{ className?: string }>][] =
	[
		[/cardio|heart/i, HeartPulse],
		[/derma|skin/i, Smile],
		[/pedia|child|baby/i, Baby],
		[/neuro|brain/i, Brain],
		[/ortho|bone/i, Bone],
		[/ophthal|eye|optic/i, Eye],
		[/dent|tooth/i, Smile],
		[/immuno|vaccine/i, Syringe],
		[/internal|medicine|physician|general/i, Stethoscope],
	];

function specialtyIcon(name: string) {
	for (const [pattern, Icon] of SPECIALTY_ICONS) {
		if (pattern.test(name)) return Icon;
	}
	return Activity;
}

// Flat pastel tile colors, cycled per category — no borders/shadows, just
// colored backgrounds like the reference mockup.
const TILE_COLORS = [
	"bg-[#FBE1E1] text-[#B4483F]",
	"bg-[#DCEFE1] text-[#2F8F5B]",
	"bg-[#FBE7D6] text-[#C2703A]",
	"bg-[#E8E1F7] text-[#6B4FBF]",
	"bg-[#DCF1EF] text-[#1F8A80]",
	"bg-[#E2DEF5] text-[#4B3B8F]",
	"bg-[#FCE4EC] text-[#B0446E]",
	"bg-[#DCEAFB] text-[#3568B5]",
];

function SectionHeading({ title, href }: { title: string; href?: string }) {
	return (
		<div className="flex items-center justify-between mb-3.5">
			<h2 className="font-bold text-lg text-[#1F2937]">{title}</h2>
			{href && (
				<a
					href={href}
					className="text-sm font-medium text-[#2AAFC4] hover:underline"
				>
					View all
				</a>
			)}
		</div>
	);
}

function SpecialtyChips({
	items,
	href,
}: {
	items: CategoryItem[];
	href?: string;
}) {
	if (!items || items.length === 0) return null;
	return (
		<div className="animate-fade-up" style={{ animationDelay: "60ms" }}>
			<SectionHeading title="Browse by Specialty" href={href} />
			<div className="grid grid-cols-4 gap-3 md:flex md:flex-wrap">
				{items.map((item, i) => {
					const Icon = specialtyIcon(item.name);
					const colors = TILE_COLORS[i % TILE_COLORS.length];
					return (
						<a
							key={item.name}
							href={item.href}
							className={
								"flex shrink-0 flex-col items-center justify-center gap-1.5 rounded-2xl px-1 py-3 text-center transition-transform active:scale-95 md:w-[104px] " +
								colors
							}
						>
							<Icon className="size-6" />
							<span className="text-[11px] font-medium leading-snug line-clamp-2">
								{item.name}
							</span>
						</a>
					);
				})}
			</div>
		</div>
	);
}

/* ── Featured Doctors cards ────────────────────────────────────────────── */

function FeaturedDoctorCard({ doc }: { doc: DoctorCard }) {
	// Local-only ♡ — visual affordance from the design; nothing is saved.
	const [liked, setLiked] = useState(false);
	const availableToday = doc.availability === "Available Today";

	return (
		<div className="relative flex w-[240px] md:w-auto shrink-0 snap-start flex-col overflow-hidden rounded-3xl bg-white">
			<a href={doc.href} className="block h-40 md:h-44 w-full bg-[#DCF4F8]">
				{doc.photoUrl ? (
					<img
						src={doc.photoUrl}
						alt={doc.name}
						className="h-full w-full object-cover"
					/>
				) : (
					<span className="flex h-full w-full items-center justify-center">
						<Stethoscope className="size-10 text-[#2AAFC4]" />
					</span>
				)}
			</a>
			<button
				type="button"
				onClick={() => setLiked((v) => !v)}
				aria-label={liked ? "Remove from favorites" : "Add to favorites"}
				aria-pressed={liked}
				className="absolute top-3 right-3 flex size-9 items-center justify-center rounded-full bg-white/95 shadow-md active:scale-90 transition-transform"
			>
				<Heart
					className={
						"size-4.5 " +
						(liked ? "fill-[#EF4444] text-[#EF4444]" : "text-[#6B7280]")
					}
				/>
			</button>
			<div className="flex flex-1 flex-col p-4">
				<a href={doc.href}>
					<p className="font-bold text-base text-[#1F2937] truncate">
						{doc.name}
					</p>
				</a>
				<p className="text-sm text-[#6B7280] truncate mt-0.5">
					{doc.specialization || "General Physician"}
				</p>
				{doc.yearsExperience != null && doc.yearsExperience > 0 && (
					<p className="text-sm text-[#6B7280] mt-0.5">
						{doc.yearsExperience}+ Years Experience
					</p>
				)}
				<div className="mt-3.5 flex items-center justify-between gap-2">
					{doc.availability ? (
						<span
							className={
								"inline-flex items-center rounded-full px-3 py-1.5 text-xs font-semibold " +
								(availableToday
									? "bg-[#E1F0E6] text-[#2F8F5B]"
									: "bg-[#DCEAFB] text-[#3568B5]")
							}
						>
							{doc.availability}
						</span>
					) : (
						<span className="inline-flex items-center rounded-full bg-[#F5F7FA] px-3 py-1.5 text-xs font-semibold text-[#6B7280]">
							View Schedule
						</span>
					)}
					<a
						href={doc.href}
						aria-label={`View ${doc.name}`}
						className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-b from-[#52C2D5] to-[#2AAFC4] text-white shadow-[0_4px_12px_rgba(42,175,196,0.4)] hover:shadow-[0_6px_16px_rgba(42,175,196,0.5)] transition-shadow"
					>
						<ArrowRight className="size-4" />
					</a>
				</div>
			</div>
		</div>
	);
}

function FeaturedDoctors({
	doctors,
	href,
}: {
	doctors: DoctorCard[];
	href?: string;
}) {
	if (!doctors || doctors.length === 0) return null;
	return (
		<div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
			<SectionHeading title="Featured Doctors" href={href} />
			<div className="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1 snap-x md:grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 md:overflow-visible">
				{doctors.map((doc) => (
					<FeaturedDoctorCard key={doc.id} doc={doc} />
				))}
			</div>
		</div>
	);
}

/* ── Page ──────────────────────────────────────────────────────────────── */

export function PatientDashboard({
	data,
	dataUrl,
}: {
	data: DashboardData;
	dataUrl: string;
}) {
	const live = usePollingData(data, dataUrl, 15000);
	const bookHref = live.searchHref || "/patient/appointments/book/";

	return (
		<div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 py-2 md:py-4">
			<WelcomeHeader
				greeting={live.greeting || "Welcome back"}
				name={live.userName}
			/>

			<SearchBar baseHref={bookHref} />

			{live.carouselSlides && live.carouselSlides.length > 0 && (
				<PromoCarousel slides={live.carouselSlides} />
			)}

			{live.categories && (
				<SpecialtyChips items={live.categories} href={live.categoriesHref} />
			)}

			{live.doctors && (
				<FeaturedDoctors doctors={live.doctors} href={live.doctorsHref} />
			)}
		</div>
	);
}
