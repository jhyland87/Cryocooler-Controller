import type { DataPoint } from '../types/telemetry';
import { TelemetryLineChart } from './TelemetryLineChart';

interface Props {
  fanSpeed:    DataPoint[];  // 0–100 %
  coolantTemp: DataPoint[];  // °C
  flowRate:    DataPoint[];  // L/min
}

export function CoolingChart({ fanSpeed, coolantTemp, flowRate }: Props) {
  const series = [
    { label: 'Fan Speed (%)',     data: fanSpeed,    color: '#4dd0e1' },
    { label: 'Coolant Temp (°C)', data: coolantTemp, color: '#ef9a9a' },
    { label: 'Flow (L/min)',      data: flowRate,    color: '#a5d6a7' },
  ];

  return (
    <TelemetryLineChart
      title=""
      series={series}
      yAxis={{ min: 0 }}
    />
  );
}
