import type { PowerChartProps } from '../types/components';
import { TelemetryLineChart } from './TelemetryLineChart';

export function PowerChart({ coldHeadVolts, coldHeadAmps, coldHeadWatts, systemVolts, systemAmps, overlays }: PowerChartProps) {
  const series = [
    { label: 'Cold Head V', data: coldHeadVolts, color: '#ce93d8' },
    { label: 'Cold Head A', data: coldHeadAmps,  color: '#f48fb1' },
    { label: 'Cold Head W', data: coldHeadWatts, color: '#ef5350' },
    { label: 'System V',    data: systemVolts,   color: '#80cbc4' },
    { label: 'System A',    data: systemAmps,    color: '#ffcc80' },
  ];

  return (
    <TelemetryLineChart
      title=""
      series={series}
      yAxis={{  }}
      overlays={overlays}
    />
  );
}
