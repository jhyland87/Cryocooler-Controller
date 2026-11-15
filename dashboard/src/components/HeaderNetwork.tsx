/**
 * @file HeaderNetwork.tsx
 * @brief Header button showing the joined WiFi network; click for the details.
 */

import type { ComponentChildren } from 'preact';
import { useState } from 'preact/hooks';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import Popover from '@mui/material/Popover';
import Typography from '@mui/material/Typography';
import type { HeaderNetworkProps } from '../types/components';
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

/** Bar meter; every bar is unlit when there is no level. */
function SignalMeter({ level }: { level?: SignalLevel }) {
  return (
    <Box sx={sx.signalMeter} aria-hidden="true">
      {Array.from({ length: SIGNAL_BARS }).map((_, barIndex) => (
        <Box
          key={barIndex}
          sx={sx.signalBar(barIndex, level !== undefined && barIndex < level.bars, level?.color ?? '')}
        />
      ))}
    </Box>
  );
}

// ─── Header network menu ──────────────────────────────────────────────────────

/** One label / value line. */
function Row({ label, children }: { label: string; children: ComponentChildren }) {
  return (
    <>
      <Typography variant="caption" sx={sx.networkLabel}>{label}</Typography>
      <Box sx={sx.networkValue}>{children}</Box>
    </>
  );
}

/** Network name in the header, with a dropdown of the connection details. */
export function HeaderNetwork({ network }: HeaderNetworkProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  const hostname = network?.hostname ? `${network.hostname}.local` : '—';
  const rssiDbm = network?.connected ? network.rssi_dbm : undefined;
  const level = rssiDbm === undefined ? undefined : signalLevel(rssiDbm);
  const name = network?.connected && network.ssid ? network.ssid : 'No WiFi';

  return (
    <>
      <ButtonBase
        sx={sx.headerNetworkButton}
        onClick={(event) => setAnchor(event.currentTarget)}
        aria-haspopup="dialog"
        aria-label={`Network: ${name}`}
      >
        <SignalMeter level={level} />
        <Box component="span" sx={sx.headerNetworkName}>{name}</Box>
        <span aria-hidden="true">▾</span>
      </ButtonBase>

      <Popover
        open={anchor !== null}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Box sx={sx.headerNetworkPopover}>
          <Box sx={sx.networkGrid}>
            <Row label="Hostname">{hostname}</Row>
            <Row label="IP address">{network?.ip || '—'}</Row>
            <Row label="WiFi network">{network?.ssid || '—'}</Row>
            <Row label="Signal">
              {level ? (
                <Box sx={sx.flexRow(1)}>
                  <SignalMeter level={level} />
                  <span>{rssiDbm} dBm · {level.label}</span>
                </Box>
              ) : '—'}
            </Row>
          </Box>
        </Box>
      </Popover>
    </>
  );
}
