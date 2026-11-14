/**
 * @file NetworkPanel.tsx
 * @brief Hostname, IP address, WiFi network and signal strength of the board.
 */

import type { ComponentChildren } from 'preact';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import type { NetworkPanelProps } from '../types/components';
import * as sx from '../theme/styles';

// ─── Signal strength ──────────────────────────────────────────────────────────

/** Bars shown in the signal meter. */
const SIGNAL_BARS = 4;

interface SignalLevel {
  /** Weakest RSSI (dBm) that still counts as this level. */
  minDbm: number;
  label: string;
  bars: number;
  color: string;
}

/** Strongest first; the last entry catches everything weaker. */
const SIGNAL_LEVELS: SignalLevel[] = [
  { minDbm: -55,       label: 'Excellent', bars: 4, color: '#66bb6a' },
  { minDbm: -67,       label: 'Good',      bars: 3, color: '#66bb6a' },
  { minDbm: -75,       label: 'Fair',      bars: 2, color: '#ffa726' },
  { minDbm: -Infinity, label: 'Weak',      bars: 1, color: '#ef5350' },
];

/** Signal level for an RSSI reading in dBm. */
function signalLevel(rssiDbm: number): SignalLevel {
  return SIGNAL_LEVELS.find((level) => rssiDbm >= level.minDbm) ?? SIGNAL_LEVELS[SIGNAL_LEVELS.length - 1];
}

// ─── Network panel ────────────────────────────────────────────────────────────

/** One label / value line. */
function Row({ label, children }: { label: string; children: ComponentChildren }) {
  return (
    <>
      <Typography variant="caption" sx={sx.networkLabel}>{label}</Typography>
      <Box sx={sx.networkValue}>{children}</Box>
    </>
  );
}

/** Network details from the latest telemetry frame. */
export function NetworkPanel({ network, loading }: NetworkPanelProps) {
  if (loading) {
    return (
      <Box sx={sx.networkGrid}>
        {Array.from({ length: 4 }).map((_, rowIndex) => (
          <Skeleton key={rowIndex} variant="text" height={20} sx={sx.networkSkeleton} />
        ))}
      </Box>
    );
  }

  const hostname = network?.hostname ? `${network.hostname}.local` : '—';
  const hasSignal = Boolean(network?.connected) && typeof network?.rssi_dbm === 'number';
  const level = hasSignal ? signalLevel(network!.rssi_dbm!) : undefined;

  return (
    <Box sx={sx.networkGrid}>
      <Row label="Hostname">{hostname}</Row>
      <Row label="IP address">{network?.ip || '—'}</Row>
      <Row label="WiFi network">{network?.ssid || '—'}</Row>
      <Row label="Signal">
        {level ? (
          <Box sx={sx.flexRow(1)}>
            <Box sx={sx.signalMeter} aria-hidden="true">
              {Array.from({ length: SIGNAL_BARS }).map((_, barIndex) => (
                <Box key={barIndex} sx={sx.signalBar(barIndex, barIndex < level.bars, level.color)} />
              ))}
            </Box>
            <span>{network!.rssi_dbm} dBm · {level.label}</span>
          </Box>
        ) : '—'}
      </Row>
    </Box>
  );
}
