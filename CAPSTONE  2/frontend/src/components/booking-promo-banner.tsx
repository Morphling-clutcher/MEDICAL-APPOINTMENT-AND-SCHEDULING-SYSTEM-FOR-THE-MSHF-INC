import { CalendarPlus } from "lucide-react";

export function BookingPromoBanner({ href }: { href: string }) {
	return (
		<a
			href={href}
			className="animate-fade-up block rounded-2xl bg-gradient-to-br from-[#17758B] via-[#1D8FA8] to-[#2AAFC4] p-5 text-white relative overflow-hidden"
			style={{ animationDelay: "60ms" }}
		>
			<div className="absolute -right-6 -bottom-6 size-28 rounded-full bg-white/10" />
			<div className="absolute right-10 -top-8 size-20 rounded-full bg-white/5" />
			<div className="relative max-w-[70%]">
				<p className="text-lg font-bold leading-snug">
					Need to see a doctor?
				</p>
				<p className="text-sm text-white/80 mt-1 mb-4">
					Book an appointment with our specialists in just a few taps.
				</p>
				<span className="inline-flex items-center gap-1.5 text-sm font-medium bg-white text-[#16404C] rounded-lg px-3.5 py-2">
					<CalendarPlus className="size-4" />
					Book Now
				</span>
			</div>
		</a>
	);
}
