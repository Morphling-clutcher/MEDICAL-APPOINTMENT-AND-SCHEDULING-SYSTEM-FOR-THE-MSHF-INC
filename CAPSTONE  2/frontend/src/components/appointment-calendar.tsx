"use client";

import { useMemo, useState } from "react";
import { parseIsoCalendarDate } from "@/components/formater";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { TrendPoint } from "@/types";

type PeriodDays = 7 | 30;

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function AppointmentCalendar({
  data,
  label,
  appointmentsHref,
}: {
  data: TrendPoint[];
  label: string;
  appointmentsHref: string;
}) {
  const [periodDays, setPeriodDays] = useState<PeriodDays>(7);

  const chartDays = useMemo(() => {
    if (data.length === 0) return [];
    const lastDate = parseIsoCalendarDate(data[data.length - 1].date);
    const startDate = new Date(lastDate);
    startDate.setDate(startDate.getDate() - periodDays + 1);
    return data.filter((item) => {
      const d = parseIsoCalendarDate(item.date);
      return d >= startDate && d <= lastDate;
    });
  }, [data, periodDays]);

  const today = todayISO();

  return (
    <Card className="animate-fade-up border-border/70 py-4 lg:col-span-3">
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-2">
            <CardTitle className="text-base">{label}</CardTitle>
            <CardDescription>
              Daily count by day, last {periodDays} days.
            </CardDescription>
          </div>
          <Select
            onValueChange={(v) => {
              const n = Number(v);
              if (n === 7 || n === 30) {
                setPeriodDays(n);
              }
            }}
            value={String(periodDays)}
          >
            <SelectTrigger
              aria-label="Calendar range"
              className="w-full min-w-36 sm:w-fit"
              size="sm"
            >
              <SelectValue placeholder="Range" />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {chartDays.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No appointment data available.
          </p>
        ) : (
          <>
            {/* Day-of-week header */}
            <div
              className="grid gap-1 mb-1 text-center"
              style={{ gridTemplateColumns: `repeat(${Math.min(chartDays.length, 7)}, 1fr)` }}
            >
              {chartDays.slice(0, Math.min(chartDays.length, 7)).map((item) => {
                const d = parseIsoCalendarDate(item.date);
                return (
                  <span
                    key={item.date}
                    className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide"
                  >
                    {d.toLocaleDateString("en-US", { weekday: "short" })}
                  </span>
                );
              })}
            </div>
            {/* Day grid */}
            <div
              className="grid gap-1"
              style={{ gridTemplateColumns: `repeat(${Math.min(chartDays.length, 7)}, 1fr)` }}
            >
              {chartDays.map((item) => {
                const isToday = item.date === today;
                const hasAppts = item.value > 0;
                return (
                  <a
                    key={item.date}
                    href={`${appointmentsHref}?date=${item.date}`}
                    className={`
                      flex flex-col items-center justify-center gap-0.5 rounded-xl px-1.5 py-2.5
                      transition cursor-pointer select-none
                      ${isToday
                        ? "bg-[#1F4D11] text-white shadow-sm"
                        : hasAppts
                          ? "bg-brand-50/60 hover:bg-brand-100 text-ink"
                          : "bg-transparent hover:bg-softgray/60 text-muted-foreground"
                      }
                    `}
                  >
                    <span className="text-[11px] font-semibold leading-none">
                      {parseIsoCalendarDate(item.date).getDate()}
                    </span>
                    {hasAppts && (
                      <span
                        className={`
                          text-[10px] font-bold leading-none mt-0.5
                          ${isToday ? "text-white" : "text-brand-700"}
                        `}
                      >
                        {item.value}
                      </span>
                    )}
                  </a>
                );
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
