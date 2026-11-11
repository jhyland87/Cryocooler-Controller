/**
 * @file HistoryRangeToggle.tsx
 * @brief Time-range picker for the line charts (2 min to the whole recorded run).
 */

import Box from '@mui/material/Box';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import type { HistoryRangeId, HistoryRangeToggleProps } from '../types/components';
import * as sx from '../theme/styles';

// ─── Ranges ───────────────────────────────────────────────────────────────────

const RANGES: ReadonlyArray<{ id: HistoryRangeId; label: string; windowMs: number | undefined }> = [
  { id: '2m',  label: '2 min',  windowMs: 120_000 },
  { id: '30m', label: '30 min', windowMs: 1_800_000 },
  { id: '4h',  label: '4 h',    windowMs: 14_400_000 },
  { id: 'all', label: 'All',    windowMs: undefined },
];

/**
 * Window length for a range id.
 *
 * @param id  Range id, e.g. '30m'.
 * @returns Window in ms, or undefined for 'all'.
 */
export function rangeWindowMs(id: HistoryRangeId): number | undefined {
  return RANGES.find((range) => range.id === id)?.windowMs;
}

/** "3 h 12 min" / "12 min" for the recorded span. */
function formatSpan(spanMs: number): string {
  const totalMin = Math.floor(spanMs / 60_000);
  const hours = Math.floor(totalMin / 60);
  return hours > 0 ? `${hours} h ${totalMin % 60} min` : `${totalMin} min`;
}

// ─── Component ────────────────────────────────────────────────────────────────

/** Range buttons plus how much history the dashboard holds. */
export function HistoryRangeToggle({ value, onChange, spanMs }: HistoryRangeToggleProps) {
  return (
    <Box sx={sx.rangeToggleRow}>
      {spanMs > 0 && (
        <Typography variant="caption" color="text.secondary">
          History: {formatSpan(spanMs)}
        </Typography>
      )}
      <ToggleButtonGroup
        size="small"
        exclusive
        value={value}
        onChange={(_event: unknown, next: HistoryRangeId | null) => {
          if (next !== null) onChange(next);
        }}
      >
        {RANGES.map((range) => (
          <ToggleButton key={range.id} value={range.id} sx={sx.rangeToggleButton}>
            {range.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
}
