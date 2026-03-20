import { LineChart } from '@mui/x-charts/LineChart';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import { useMemo, useState, useCallback } from 'preact/hooks';
import type { DataPoint } from '../types/telemetry';
import type { TelemetryLineChartProps } from '../types/components';
import { useContainerWidth, calcTickStep } from '../hooks/useContainerWidth';
import { HISTORY_WINDOW_MS } from '../hooks/useHistoryBuffer';
import { createTimeFormatter } from '../utils/formatters';
import * as sx from '../theme/styles';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function padTo(arr: (number | null)[], len: number): (number | null)[] {
  const out: (number | null)[] = [...arr];
  while (out.length < len) out.unshift(null);
  return out;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function TelemetryLineChart({ title, series, yAxis }: TelemetryLineChartProps) {
  const loading = series.every((s) => s.data.length === 0);
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const tickStep = calcTickStep(containerWidth);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());

  const toggleSeries = useCallback((label: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  }, []);

  const visibleSeries = series.filter((s) => !hidden.has(s.label));

  const longest = series.reduce<DataPoint[]>(
    (best, s) => (s.data.length >= best.length ? s.data : best),
    [],
  );

  const xData        = longest.map((p) => p.t);
  const timeFormatter = useMemo(() => createTimeFormatter(), [xData.length > 0 ? xData[0] : 0]);

  const n    = xData.length || 1;
  const xMax = longest.length > 0 ? longest[longest.length - 1].t : Date.now();
  const xMin = xMax - HISTORY_WINDOW_MS;

  const PADDING = 10;

  const yMin: number | undefined = (() => {
    const allValues = visibleSeries.flatMap((s) => s.data.map((p) => p.v)).filter((v): v is number => v !== null);
    if (allValues.length === 0) return yAxis?.min ?? 0;
    const dataMin = Math.min(...allValues);
    return Math.floor(dataMin - PADDING);
  })();

  const yMax: number | undefined = (() => {
    const allValues = visibleSeries.flatMap((s) => s.data.map((p) => p.v)).filter((v): v is number => v !== null);
    if (allValues.length === 0) return yAxis?.max ?? 1;
    const dataMax = Math.max(...allValues);
    return Math.ceil(dataMax + PADDING);
  })();

  const chartSeries = visibleSeries.map((s) => ({
    label:    s.label,
    data:     padTo(s.data.map((p) => p.v), n),
    color:    s.color,
    showMark: false,
    id:       s.label.replace(/[^a-zA-Z0-9]/g, '_'),
  }));

  // Build sx overrides for dashed series
  const dashedIds = visibleSeries
    .filter((s) => s.dashed)
    .map((s) => s.label.replace(/[^a-zA-Z0-9]/g, '_'));
  const dashedSx = dashedIds.length > 0
    ? Object.fromEntries(
        dashedIds.map((id) => [
          `& .MuiLineElement-series-${id}`,
          { strokeDasharray: '6 4' },
        ])
      )
    : {};

  if (loading) {
    return (
      <Box ref={containerRef} sx={sx.chartContainer}>
        <Box sx={sx.chartLegendRow}>
          {title && <Skeleton variant="text" width={title.length * 7} height={16} sx={sx.skeletonChartTitle} />}
          {series.map((s) => (
            <Skeleton key={s.label} variant="rounded" width={70} height={22} sx={sx.skeletonLegendChip} />
          ))}
        </Box>
        <Skeleton variant="rounded" height={220} />
      </Box>
    );
  }

  return (
    <Box ref={containerRef} sx={sx.chartContainer}>
      <Box sx={sx.chartLegendRow}>
        {title && (
          <Typography variant="subtitle2" sx={sx.chartTitle}>
            {title}
          </Typography>
        )}
        {series.map((s) => {
          const isVisible = !hidden.has(s.label);
          return (
            <Box
              key={s.label}
              onClick={() => toggleSeries(s.label)}
              sx={sx.legendToggle(isVisible, s.color)}
            >
              <Box sx={sx.legendDotSmall(isVisible, s.color)} />
              <Typography sx={sx.legendToggleLabel(isVisible)}>
                {s.label}
              </Typography>
            </Box>
          );
        })}
      </Box>

      <LineChart
        xAxis={[{
          data:           xData.length > 0 ? xData : [xMax],
          min:            xMin,
          max:            xMax,
          scaleType:      'linear',
          valueFormatter: timeFormatter,
          tickMinStep:    tickStep,
        }]}
        yAxis={[{
          min:            yMin,
          max:            yMax,
          valueFormatter: (v: number) => {
            if (v % 1 === 0) return String(v);
            const s = v.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
            return s;
          },
        }]}
        series={chartSeries}
        height={220}
        skipAnimation
        slotProps={{ legend: { hidden: true } }}
        margin={{ top: 10, right: 10, bottom: 36, left: 52 }}
        grid={{ horizontal: true }}
        sx={dashedSx}
      />
    </Box>
  );
}
