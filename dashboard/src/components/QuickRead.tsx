/**
 * @file QuickRead.tsx
 * @brief Numeric tiles for the latest telemetry values, in labelled groups.
 */

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import type { QuickReadProps, TileConfig } from '../types/components';
import type { DataPoint, TelemetryData } from '../types/telemetry';
import { getField } from '../types/telemetry';
import * as sx from '../theme/styles';

// ─── Trend background ─────────────────────────────────────────────────────────

/** Side of the square SVG viewBox the trend is drawn in. */
const TREND_SIZE = 100;

/** Share of the tile height left clear above and below the line. */
const TREND_MARGIN = 0.12;

/**
 * SVG path for a trend line, scaled to the viewBox. Null points break the line,
 * so missing readings show as gaps like in the main charts.
 */
function trendPath(points: DataPoint[], windowMs?: number): string {
  const values = points.flatMap((point) => (point.v === null ? [] : [point.v]));
  if (values.length < 2) return '';

  const endMs = points[points.length - 1].t;
  const startMs = windowMs === undefined ? points[0].t : endMs - windowMs;
  const spanMs = Math.max(1, endMs - startMs);
  const min = Math.min(...values);
  const range = Math.max(...values) - min;
  const usable = TREND_SIZE * (1 - 2 * TREND_MARGIN);

  let path = '';
  let penDown = false;
  for (const point of points) {
    if (point.v === null) {
      penDown = false;
      continue;
    }
    const x = ((point.t - startMs) / spanMs) * TREND_SIZE;
    // A flat series sits on the centre line.
    const level = range === 0 ? 0.5 : (point.v - min) / range;
    const y = TREND_SIZE * (1 - TREND_MARGIN) - level * usable;
    path += `${penDown ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`;
    penDown = true;
  }
  return path;
}

/** Faint history line behind a tile's value. */
function TileTrend({ points, color, windowMs }: { points: DataPoint[]; color: string; windowMs?: number }) {
  const path = trendPath(points, windowMs);
  if (path === '') return null;
  return (
    <Box
      component="svg"
      viewBox={`0 0 ${TREND_SIZE} ${TREND_SIZE}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      sx={sx.quickReadTrend}
    >
      <path d={path} fill="none" stroke={color} stroke-width={2} vector-effect="non-scaling-stroke" />
    </Box>
  );
}

// ─── Tiles ────────────────────────────────────────────────────────────────────

interface TileProps {
  tile: TileConfig;
  data: TelemetryData;
  points: DataPoint[];
  windowMs?: number;
  loading?: boolean;
}

/** One value tile; a dash when the field has no reading. */
function Tile({ tile, data, points, windowMs, loading }: TileProps) {
  if (loading) {
    return (
      <Box sx={sx.quickReadTile}>
        <Skeleton variant="text" width={50} height={28} sx={sx.skeletonCentered} />
        <Skeleton variant="text" width={24} height={10} sx={sx.skeletonCentered} />
        <Skeleton variant="text" width={54} height={10} sx={sx.skeletonCentered} />
      </Box>
    );
  }

  const value = getField(data, tile.key);
  return (
    <Box sx={sx.quickReadTile}>
      <TileTrend points={points} color={tile.color} windowMs={windowMs} />
      <Typography sx={sx.tileValueColored(tile.color)}>
        {typeof value === 'number' ? value.toFixed(tile.dp) : '—'}
      </Typography>
      <Typography variant="caption" sx={sx.tileUnit}>{tile.unit}</Typography>
      <Typography variant="caption" sx={sx.tileLabel}>{tile.label}</Typography>
    </Box>
  );
}

/** Tile groups, each under its own heading. */
export function QuickRead({ groups, data, trend, windowMs, loading }: QuickReadProps) {
  return (
    <Box sx={sx.quickReadGroups}>
      {groups.map((group) => (
        <Box key={group.title}>
          <Typography variant="caption" sx={sx.quickReadGroupTitle}>{group.title}</Typography>
          <Box sx={sx.quickReadContainer}>
            {group.tiles.map((tile) => (
              <Tile
                key={tile.key}
                tile={tile}
                data={data}
                points={trend(tile.key)}
                windowMs={windowMs}
                loading={loading}
              />
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}
