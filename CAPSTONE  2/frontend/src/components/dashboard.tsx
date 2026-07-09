import { AppointmentCalendar } from "@/components/appointment-calendar";
import { DashboardStats } from "@/components/stats";
import { Categories } from "@/components/categories";
import { OurDoctors } from "@/components/our-doctors";
import { DoctorSearchBar } from "@/components/doctor-search-bar";
import { PromoCarousel } from "@/components/promo-carousel";
import { usePollingData } from "@/hooks/use-polling-data";
import type { DashboardData } from "@/types";

export function Dashboard({
	data,
	dataUrl,
}: {
	data: DashboardData;
	dataUrl: string;
}) {
	const live = usePollingData(data, dataUrl, 15000);
	const firstName = live.userName?.split(" ")[0];
	const greetingWord = live.greeting || "Welcome back";

	return (
		<div className="flex flex-1 flex-col gap-6 py-6">
			<div className="flex flex-col gap-1">
				<h1 className="font-semibold text-xl leading-tight">
					{firstName ? `${greetingWord}, ${firstName}!` : `${greetingWord}!`}
				</h1>
				<p className="text-base text-muted-foreground">
					let's get things done.
				</p>
			</div>

			{live.searchHref && <DoctorSearchBar baseHref={live.searchHref} />}

			{live.carouselSlides && live.carouselSlides.length > 0 && (
				<PromoCarousel slides={live.carouselSlides} />
			)}

			{live.categories && (
				<Categories items={live.categories} href={live.categoriesHref} />
			)}

			<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
				<DashboardStats stats={live.stats} />
			</div>

			{live.trend && (
				<AppointmentCalendar
					data={live.trend}
					label={live.trendLabel || "Appointments"}
					appointmentsHref={live.appointmentsHref || "/doctor/appointments/"}
				/>
			)}

			{live.doctors && (
				<OurDoctors doctors={live.doctors} href={live.doctorsHref} />
			)}
		</div>
	);
}
