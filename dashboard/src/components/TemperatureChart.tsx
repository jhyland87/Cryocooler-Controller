import type { DataPoint } from '../types/telemetry';
import { TelemetryLineChart } from './TelemetryLineChart';

interface Props {
  actualC:  DataPoint[];
  ambientC: DataPoint[];
  /** Optional delta-below-ambient series. */
  deltaC?:  DataPoint[];
}

export function TemperatureChart({ actualC, ambientC, deltaC }: Props) {
  const series = [
    { label: 'Actual (°C)',    data: actualC,  color: '#29b6f6' },
    { label: 'Ambient (°C)',   data: ambientC, color: '#ffa726' },
    ...(deltaC && deltaC.length > 0
      ? [{ label: 'Δ Below Ambient', data: deltaC, color: '#66bb6a' }]
      : []),
  ];

  return (
    <TelemetryLineChart
      title="Cold Head Temperature"
      series={series}
      yAxis={{ min: -200, max: 40 }}
    />
  );
}
