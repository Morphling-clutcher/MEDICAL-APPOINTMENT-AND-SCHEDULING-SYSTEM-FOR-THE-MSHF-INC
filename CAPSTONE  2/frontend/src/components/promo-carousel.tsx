import { useEffect, useRef, useState } from "react";
import { CalendarPlus, Users, ShieldCheck } from "lucide-react";

export type CarouselSlide = {
	id: string;
	title: string;
	description: string;
	ctaLabel: string;
	href: string;
	icon: "calendar" | "doctors" | "shield";
	theme: "navy" | "teal" | "violet";
};

const ICONS = {
	calendar: CalendarPlus,
	doctors: Users,
	shield: ShieldCheck,
};

// Tailwind's scanner only finds class names that appear as literal strings in
// source — it can't see classes built from data that came over the wire
// (e.g. from a JSON API). So slide gradients are picked from this fixed,
// fully-written-out lookup by a short "theme" key, rather than letting the
// backend send a raw Tailwind class string that would never get compiled.
const THEMES: Record<CarouselSlide["theme"], string> = {
	navy: "bg-gradient-to-br from-[#17758B] via-[#1D8FA8] to-[#2AAFC4]",
	teal: "bg-gradient-to-br from-[#1F7A93] via-[#2697B3] to-[#3FB8D3]",
	violet: "bg-gradient-to-br from-[#524699] via-[#5E51A8] to-[#6B5FB8]",
};

export function PromoCarousel({
	slides,
	intervalMs = 5000,
}: {
	slides: CarouselSlide[];
	intervalMs?: number;
}) {
	const [index, setIndex] = useState(0);
	const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const touchStartX = useRef<number | null>(null);

	useEffect(() => {
		if (slides.length <= 1) return;
		timerRef.current = setInterval(() => {
			setIndex((i) => (i + 1) % slides.length);
		}, intervalMs);
		return () => {
			if (timerRef.current) clearInterval(timerRef.current);
		};
	}, [slides.length, intervalMs]);

	const restartTimer = () => {
		if (timerRef.current) clearInterval(timerRef.current);
		if (slides.length <= 1) return;
		timerRef.current = setInterval(() => {
			setIndex((i) => (i + 1) % slides.length);
		}, intervalMs);
	};

	const goTo = (i: number) => {
		setIndex(((i % slides.length) + slides.length) % slides.length);
		restartTimer();
	};

	if (!slides || slides.length === 0) return null;

	return (
		<div
			className="animate-fade-up relative"
			style={{ animationDelay: "60ms" }}
			onTouchStart={(e) => {
				touchStartX.current = e.touches[0].clientX;
			}}
			onTouchEnd={(e) => {
				if (touchStartX.current === null) return;
				const delta = e.changedTouches[0].clientX - touchStartX.current;
				if (Math.abs(delta) > 40) {
					goTo(index + (delta < 0 ? 1 : -1));
				}
				touchStartX.current = null;
			}}
		>
			<div className="relative overflow-hidden rounded-2xl">
				<div
					className="flex transition-transform duration-500 ease-out"
					style={{ transform: `translateX(-${index * 100}%)` }}
				>
					{slides.map((slide) => {
						const Icon = ICONS[slide.icon];
						const gradientClass = THEMES[slide.theme] ?? THEMES.navy;
						return (
							<a
								key={slide.id}
								href={slide.href}
								className={`w-full shrink-0 p-5 text-white relative overflow-hidden ${gradientClass}`}
							>
								<div className="absolute -right-6 -bottom-6 size-28 rounded-full bg-white/10" />
								<div className="absolute right-10 -top-8 size-20 rounded-full bg-white/5" />
								<div className="relative max-w-[70%]">
									<p className="text-lg font-bold leading-snug">
										{slide.title}
									</p>
									<p className="text-sm text-white/80 mt-1 mb-4">
										{slide.description}
									</p>
									<span className="inline-flex items-center gap-1.5 text-sm font-medium bg-white rounded-lg px-3.5 py-2 text-[#1F2937]">
										<Icon className="size-4" />
										{slide.ctaLabel}
									</span>
								</div>
							</a>
						);
					})}
				</div>
			</div>
			{slides.length > 1 && (
				<div className="flex items-center justify-center gap-1.5 mt-3">
					{slides.map((slide, i) => (
						<button
							key={slide.id}
							type="button"
							aria-label={`Go to slide ${i + 1}`}
							onClick={() => goTo(i)}
							className={`h-1.5 rounded-full transition-all ${
								i === index ? "w-6 bg-[#1F2937]" : "w-1.5 bg-[#D1D5DB]"
							}`}
						/>
					))}
				</div>
			)}
		</div>
	);
}
