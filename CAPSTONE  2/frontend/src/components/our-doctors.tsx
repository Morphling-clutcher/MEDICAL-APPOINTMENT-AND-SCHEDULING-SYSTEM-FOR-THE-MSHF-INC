import { Stethoscope } from "lucide-react";
import type { DoctorCard } from "@/types";

export function OurDoctors({
	doctors,
	href,
}: {
	doctors: DoctorCard[];
	href?: string;
}) {
	if (!doctors || doctors.length === 0) return null;

	return (
		<div className="animate-fade-up" style={{ animationDelay: "180ms" }}>
			<div className="flex items-center justify-between mb-3">
				<h2 className="font-semibold text-base text-[#1F2937]">Our Doctors</h2>
				{href && (
					<a href={href} className="text-sm text-[#2AAFC4] hover:underline">
						See All
					</a>
				)}
			</div>
			<div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1 snap-x">
				{doctors.map((doc) => (
					<a
						key={doc.id}
						href={doc.href}
						className="flex-shrink-0 w-36 snap-start rounded-2xl border border-border/70 bg-card overflow-hidden hover:shadow-md transition-shadow"
					>
						<div className="h-28 w-full bg-[#DCF4F8] flex items-center justify-center overflow-hidden">
							{doc.photoUrl ? (
								<img
									src={doc.photoUrl}
									alt={doc.name}
									className="h-full w-full object-cover"
								/>
							) : (
								<Stethoscope className="size-8 text-[#2AAFC4]" />
							)}
						</div>
						<div className="p-2.5">
							<p className="text-sm font-semibold text-[#1F2937] truncate">
								{doc.name}
							</p>
							<p className="text-xs text-[#4B5563] truncate">
								{doc.specialization || "General"}
							</p>
						</div>
					</a>
				))}
			</div>
		</div>
	);
}
