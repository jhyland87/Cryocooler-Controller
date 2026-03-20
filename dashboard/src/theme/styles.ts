import type { SxProps, Theme } from '@mui/material/styles';

// ─── Layout ─────────────────────────────────────────────────────────────────

/** Full-height column layout for the app shell. */
export const appShell: SxProps<Theme> = {
  minHeight: '100vh',
  bgcolor: 'background.default',
  display: 'flex',
  flexDirection: 'column',
};

/** Centred loading screen. */
export const loadingScreen: SxProps<Theme> = {
  minHeight: '100vh',
  bgcolor: 'background.default',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 2.5,
};

/** Connection-lost overlay covering the viewport. */
export const disconnectedOverlay: SxProps<Theme> = {
  position: 'absolute',
  inset: 0,
  height: '100vh',
  width: '100vw',
  zIndex: 50,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  bgcolor: 'rgba(238, 242, 247, 0.85)',
  backdropFilter: 'blur(2px)',
  gap: 1.5,
  borderRadius: 1,
};

/** Main content area with responsive padding. */
export const mainContent: SxProps<Theme> = {
  flex: 1,
  p: { xs: 1.5, sm: 2 },
  position: 'relative',
};

// ─── Card / Container ───────────────────────────────────────────────────────

/** Standard bordered card container — used by SparkCard, MultiSparkCard,
 *  VibrationWave, CollapsiblePanel, etc. */
export const card: SxProps<Theme> = {
  bgcolor: 'background.paper',
  borderRadius: 1,
  border: '1px solid',
  borderColor: 'divider',
  overflow: 'hidden',
};

/** Card container with padding — SparkCard, MultiSparkCard, VibrationWave. */
export const paddedCard: SxProps<Theme> = {
  ...card as object,
  p: 1.5,
};

/** Spark-card specific sizing. */
export const sparkCardRoot: SxProps<Theme> = {
  ...paddedCard as object,
  flex: '1 1 140px',
  minWidth: 120,
};

/** Vibration wave card sizing. */
export const vibrationCardRoot: SxProps<Theme> = {
  ...paddedCard as object,
  flex: '1 1 240px',
  minWidth: 200,
};

/** Quick-read tile in the App overview. */
export const quickReadTile: SxProps<Theme> = {
  flex: '1 1 90px',
  minWidth: 80,
  bgcolor: 'background.paper',
  borderRadius: 1,
  p: 1.25,
  border: '1px solid',
  borderColor: 'divider',
  textAlign: 'center',
};

/** CSS Grid cell — children fill the cell regardless of their own flex/minWidth. */
export const gridCell: SxProps<Theme> = {
  minWidth: 0,
  '& > *': { flex: 'none', minWidth: 0, width: '100%', height: '100%' },
};

// ─── Header rows ────────────────────────────────────────────────────────────

/** Flex header row with space-between — used in SparkCard, MultiSparkCard,
 *  VibrationWave, TelemetryLineChart. */
export const cardHeader: SxProps<Theme> = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  mb: 0.5,
};

/** Flex row with gap — used for chart legend, pagination, etc. */
export const flexRow = (gap: number = 1): SxProps<Theme> => ({
  display: 'flex',
  alignItems: 'center',
  gap,
});

// ─── Typography ─────────────────────────────────────────────────────────────

/** Uppercase section label — used in SparkCard, MultiSparkCard,
 *  VibrationWave, CollapsiblePanel, ConsoleLog, TelemetryLineChart. */
export const sectionLabel: SxProps<Theme> = {
  color: 'text.secondary',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.8,
  fontSize: '0.65rem',
};

/** Same as sectionLabel but at 0.7rem — used in CollapsiblePanel header,
 *  ConsoleLog, TelemetryLineChart title. */
export const panelTitle: SxProps<Theme> = {
  color: 'text.secondary',
  fontWeight: 600,
  letterSpacing: 1,
  textTransform: 'uppercase',
  fontSize: '0.7rem',
};

/** Monospace value display in quick-read tiles. */
export const tileValue: SxProps<Theme> = {
  fontSize: '1.2rem',
  fontWeight: 700,
  lineHeight: 1.1,
  fontFamily: 'monospace',
};

/** Small unit label under tile values. */
export const tileUnit: SxProps<Theme> = {
  color: 'text.disabled',
  fontSize: '0.6rem',
  display: 'block',
};

/** Small uppercase label under tile values. */
export const tileLabel: SxProps<Theme> = {
  color: 'text.secondary',
  fontSize: '0.62rem',
  letterSpacing: 0.5,
  textTransform: 'uppercase',
};

// ─── Header bar (AppBar) ────────────────────────────────────────────────────

export const headerAppBar: SxProps<Theme> = {
  bgcolor: '#0d1117',
  borderBottom: '1px solid rgba(255,255,255,0.08)',
};

export const headerToolbar: SxProps<Theme> = {
  gap: 2,
  flexWrap: 'wrap',
  minHeight: { xs: 56 },
};

export const headerTitle: SxProps<Theme> = {
  fontWeight: 700,
  letterSpacing: 1,
  fontSize: '1rem',
  color: '#90caf9',
  flexShrink: 0,
};

export const headerStateChip: SxProps<Theme> = {
  bgcolor: '#1565c0',
  color: '#fff',
  fontWeight: 700,
  fontSize: '0.72rem',
  letterSpacing: 0.5,
};

export const headerStatusText: SxProps<Theme> = {
  color: 'rgba(255,255,255,0.55)',
  flexShrink: 0,
  maxWidth: 240,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

export const headerCooldownLabel: SxProps<Theme> = {
  color: 'rgba(255,255,255,0.5)',
  fontSize: '0.65rem',
};

export const headerCooldownTrack: SxProps<Theme> = {
  width: 80,
  height: 6,
  bgcolor: 'rgba(255,255,255,0.1)',
  borderRadius: 3,
  overflow: 'hidden',
};

export const headerCooldownBar: SxProps<Theme> = {
  height: '100%',
  bgcolor: '#29b6f6',
  borderRadius: 3,
  transition: 'width 0.5s ease',
};

export const headerCooldownPct: SxProps<Theme> = {
  color: '#29b6f6',
  fontSize: '0.65rem',
  fontWeight: 700,
};

export const headerDurationLabel: SxProps<Theme> = {
  display: 'block',
  color: 'rgba(255,255,255,0.35)',
  fontSize: '0.6rem',
  lineHeight: 1,
};

export const headerDurationValue: SxProps<Theme> = {
  fontFamily: 'monospace',
  color: 'rgba(255,255,255,0.7)',
  fontSize: '0.78rem',
};

export const headerFrameCounter: SxProps<Theme> = {
  color: 'rgba(255,255,255,0.25)',
  fontSize: '0.6rem',
  fontFamily: 'monospace',
};

export const headerConnectionChip: SxProps<Theme> = {
  fontSize: '0.65rem',
  height: 20,
  flexShrink: 0,
};

export const headerClock: SxProps<Theme> = {
  color: 'rgba(255,255,255,0.6)',
  fontFamily: 'monospace',
  fontSize: '0.85rem',
};

// ─── Status panel ───────────────────────────────────────────────────────────

export const ledContainer: SxProps<Theme> = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 0.5,
};

export const ledDot = (active: boolean, color: string): SxProps<Theme> => ({
  width: 18,
  height: 18,
  borderRadius: '50%',
  bgcolor: active ? color : 'action.disabled',
  boxShadow: active ? `0 0 8px 2px ${color}` : 'none',
  transition: 'all 0.3s ease',
  border: '2px solid',
  borderColor: active ? color : 'divider',
});

export const ledLabel = (active: boolean, color: string): SxProps<Theme> => ({
  fontSize: '0.6rem',
  fontWeight: active ? 700 : 400,
  color: active ? color : 'text.disabled',
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  lineHeight: 1,
});

export const faultCounterBox = (hasValue: boolean): SxProps<Theme> => ({
  flex: '1 1 80px',
  textAlign: 'center',
  bgcolor: hasValue ? 'error.dark' : 'action.selected',
  borderRadius: 1,
  py: 0.75,
  px: 1,
  transition: 'background-color 0.3s',
});

export const faultCounterValue = (hasValue: boolean): SxProps<Theme> => ({
  lineHeight: 1,
  fontWeight: 700,
  color: hasValue ? '#fff' : 'text.secondary',
});

export const faultCounterLabel = (hasValue: boolean): SxProps<Theme> => ({
  fontSize: '0.6rem',
  color: hasValue ? 'rgba(255,255,255,0.7)' : 'text.disabled',
  letterSpacing: 0.5,
});

// ─── Spark card ─────────────────────────────────────────────────────────────

export const sparkGaugeBar: SxProps<Theme> = {
  mb: 0.75,
  height: 4,
  borderRadius: 2,
  bgcolor: 'action.disabledBackground',
};

export const sparklineStroke: SxProps<Theme> = {
  '& .MuiLineElement-root': { strokeWidth: 1.5 },
};

// ─── Multi-spark card ───────────────────────────────────────────────────────

export const legendDot = (color: string): SxProps<Theme> => ({
  width: 8,
  height: 8,
  borderRadius: '50%',
  bgcolor: color,
  flexShrink: 0,
});

export const overlayLayer = (isFirst: boolean): SxProps<Theme> => ({
  position: isFirst ? 'relative' : 'absolute',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
});

export const sparklineOverlayStyles: SxProps<Theme> = {
  '& .MuiLineElement-root': { strokeWidth: 1.5 },
  '& .MuiAreaElement-root': { opacity: 0 },
};

// ─── Telemetry line chart ───────────────────────────────────────────────────

export const legendToggle = (isVisible: boolean, color: string): SxProps<Theme> => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 0.5,
  cursor: 'pointer',
  userSelect: 'none',
  px: 0.75,
  py: 0.25,
  borderRadius: 1,
  border: '1px solid',
  borderColor: isVisible ? color : 'divider',
  opacity: isVisible ? 1 : 0.4,
  transition: 'opacity 0.15s, border-color 0.15s',
  '&:hover': { opacity: isVisible ? 0.85 : 0.6 },
});

export const legendDotSmall = (isVisible: boolean, color: string): SxProps<Theme> => ({
  width: 8,
  height: 8,
  borderRadius: '50%',
  bgcolor: isVisible ? color : 'text.disabled',
});

// ─── Collapsible panel ──────────────────────────────────────────────────────

export const collapsibleHeader: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  px: 1.5,
  py: 0.75,
  cursor: 'pointer',
  userSelect: 'none',
  '&:hover': { bgcolor: 'action.hover' },
};

export const collapsibleToggle: SxProps<Theme> = {
  p: 0.25,
  color: 'text.disabled',
  fontSize: '0.85rem',
};

export const collapsibleBody: SxProps<Theme> = {
  px: 1.5,
  pb: 1.5,
};

// ─── Console log ────────────────────────────────────────────────────────────

export const consoleBadge: SxProps<Theme> = {
  height: 18,
  fontSize: '0.6rem',
  bgcolor: 'action.hover',
  color: 'text.secondary',
};

export const consoleLiveChip: SxProps<Theme> = {
  height: 18,
  fontSize: '0.6rem',
  cursor: 'pointer',
  bgcolor: 'rgba(79,195,247,0.12)',
  color: '#4fc3f7',
  border: '1px solid rgba(79,195,247,0.3)',
  '&:hover': { bgcolor: 'rgba(79,195,247,0.2)' },
};

export const consoleClearBtn: SxProps<Theme> = {
  p: 0.5,
  color: 'text.disabled',
  '&:hover': { color: 'text.secondary' },
};

export const consoleTerminal: SxProps<Theme> = {
  height: 240,
  overflowY: 'auto',
  bgcolor: '#0d1117',
  borderRadius: 1,
  p: '10px 14px',
  fontFamily: '"Fira Code", "Cascadia Code", "JetBrains Mono", "Consolas", monospace',
  fontSize: '0.72rem',
  lineHeight: 1.65,
  '&::-webkit-scrollbar':       { width: 5 },
  '&::-webkit-scrollbar-thumb': { backgroundColor: '#30363d', borderRadius: 3 },
  '&::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
};

export const consoleEmpty: SxProps<Theme> = {
  color: '#484f58',
  fontFamily: 'inherit',
  fontSize: 'inherit',
};

export const consoleTimestamp: SxProps<Theme> = {
  color: '#484f58',
  fontFamily: 'inherit',
  fontSize: 'inherit',
  flexShrink: 0,
  userSelect: 'none',
  minWidth: '7ch',
};

export const consoleMessage = (color: string): SxProps<Theme> => ({
  color,
  fontFamily: 'inherit',
  fontSize: 'inherit',
  wordBreak: 'break-word',
  whiteSpace: 'pre-wrap',
  minWidth: 0,
});

export const consoleClearIcon: SxProps<Theme> = {
  fontSize: '0.75rem',
  lineHeight: 1,
  fontFamily: 'monospace',
};

// ─── Fault history panel ────────────────────────────────────────────────────

export const faultRow = (active: boolean): SxProps<Theme> => ({
  display: 'flex',
  alignItems: 'center',
  gap: 1.5,
  px: 1.25,
  py: 0.75,
  borderRadius: 0.75,
  borderLeft: '3px solid',
  borderLeftColor: active ? 'error.main' : 'success.light',
  bgcolor: active ? 'rgba(239,83,80,0.06)' : 'action.hover',
  fontSize: '0.75rem',
  overflow: 'hidden',
});

export const faultReason = (active: boolean): SxProps<Theme> => ({
  fontFamily: 'monospace',
  fontWeight: 600,
  fontSize: '0.72rem',
  color: active ? 'error.main' : 'text.primary',
  minWidth: 0,
  flexShrink: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

export const faultActiveBadge: SxProps<Theme> = {
  fontWeight: 700,
  color: '#fff',
  bgcolor: 'error.main',
  px: 0.75,
  py: 0.15,
  borderRadius: 0.5,
  fontSize: '0.62rem',
  letterSpacing: 0.5,
  flexShrink: 0,
  whiteSpace: 'nowrap',
};

export const faultPaginationBtn: SxProps<Theme> = {
  fontSize: '0.75rem',
  width: 28,
  height: 28,
};

// ─── Accel sparklines ───────────────────────────────────────────────────────

export const motionChip = (motion: boolean): SxProps<Theme> => ({
  fontSize: '0.6rem',
  height: 18,
  bgcolor: motion ? 'warning.dark' : 'success.dark',
  color: '#fff',
  fontWeight: 700,
  letterSpacing: 0.8,
});

export const motionChipWrapper: SxProps<Theme> = {
  mb: 1,
};

export const accelGrid: SxProps<Theme> = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, 1fr)',
  gridTemplateRows: '1fr 1fr',
  gap: 1,
};

// ─── App layout ─────────────────────────────────────────────────────────────

export const loadingTitle: SxProps<Theme> = {
  fontWeight: 500,
};

export const disconnectedTitle: SxProps<Theme> = {
  fontWeight: 600,
};

export const faultHistorySpacer: SxProps<Theme> = {
  mt: 2,
};

export const quickReadContainer: SxProps<Theme> = {
  display: 'flex',
  gap: 1.5,
  flexWrap: 'wrap',
  alignContent: 'flex-start',
};

export const tileValueColored = (color: string): SxProps<Theme> => ({
  ...tileValue as object,
  color,
});

// ─── Header bar (additional) ────────────────────────────────────────────────

export const headerCooldownGroup: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  gap: 0.75,
  flexShrink: 0,
};

export const headerCooldownBarFill = (pct: number): SxProps<Theme> => ({
  ...headerCooldownBar as object,
  width: `${pct}%`,
});

export const headerSpacer: SxProps<Theme> = {
  flex: 1,
};

export const headerDurationGroup: SxProps<Theme> = {
  display: 'flex',
  gap: 2,
  alignItems: 'center',
};

export const headerDurationBlock: SxProps<Theme> = {
  textAlign: 'right',
};

// ─── Status panel (additional) ──────────────────────────────────────────────

export const ledRow: SxProps<Theme> = {
  display: 'flex',
  gap: 2.5,
  flexWrap: 'wrap',
  mb: 2,
};

export const faultCounterRow: SxProps<Theme> = {
  display: 'flex',
  gap: 1.5,
  flexWrap: 'wrap',
};

// ─── Spark card (additional) ────────────────────────────────────────────────

export const sparkCardWarn = (warn: boolean): SxProps<Theme> => ({
  ...sparkCardRoot as object,
  borderColor: warn ? 'warning.dark' : 'divider',
});

export const sparkCurrentValue = (warn: boolean, color: string): SxProps<Theme> => ({
  color: warn ? 'warning.light' : color,
  fontWeight: 700,
  fontSize: '0.75rem',
});

export const sparkGaugeBarWithColor = (warn: boolean, color: string): SxProps<Theme> => ({
  ...sparkGaugeBar as object,
  '& .MuiLinearProgress-bar': { bgcolor: warn ? 'warning.main' : color },
});

// ─── Multi-spark card (additional) ──────────────────────────────────────────

export const legendChipRow: SxProps<Theme> = {
  display: 'flex',
  gap: 1.5,
  mb: 0.5,
  flexWrap: 'wrap',
};

export const legendChipItem: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  gap: 0.4,
};

export const legendChipLabel: SxProps<Theme> = {
  fontSize: '0.62rem',
  color: 'text.secondary',
  fontWeight: 600,
};

export const legendChipValue = (color: string): SxProps<Theme> => ({
  fontSize: '0.68rem',
  color,
  fontWeight: 700,
});

export const overlayContainer: SxProps<Theme> = {
  position: 'relative',
  height: 60,
};

// ─── Vibration wave (additional) ────────────────────────────────────────────

export const vibrationFreqValue: SxProps<Theme> = {
  color: '#ab47bc',
  fontWeight: 700,
  fontSize: '0.75rem',
};

// ─── Telemetry line chart (additional) ──────────────────────────────────────

export const chartContainer: SxProps<Theme> = {
  width: '100%',
  height: 280,
};

export const chartLegendRow: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  mb: 0.5,
  gap: 1,
  flexWrap: 'wrap',
};

export const chartTitle: SxProps<Theme> = {
  ...panelTitle as object,
  mr: 1,
};

export const legendToggleLabel = (isVisible: boolean): SxProps<Theme> => ({
  fontSize: '0.65rem',
  color: isVisible ? 'text.primary' : 'text.disabled',
});

// ─── System sparklines ──────────────────────────────────────────────────────

export const sparkWrapRow: SxProps<Theme> = {
  display: 'flex',
  gap: 1,
  flexWrap: 'wrap',
};

// ─── Console log (additional) ───────────────────────────────────────────────

export const consoleHeaderRow: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  mb: 1,
  gap: 1,
};

export const consoleTitle: SxProps<Theme> = {
  ...panelTitle as object,
  flex: 1,
};

export const consoleEntryRow: SxProps<Theme> = {
  display: 'flex',
  gap: '10px',
  alignItems: 'baseline',
  minWidth: 0,
};

// ─── Fault history panel (additional) ───────────────────────────────────────

export const faultList: SxProps<Theme> = {
  display: 'flex',
  flexDirection: 'column',
  gap: 0.75,
};

export const faultTimestamp: SxProps<Theme> = {
  color: 'text.secondary',
  whiteSpace: 'nowrap',
  flexShrink: 0,
};

export const faultArrow: SxProps<Theme> = {
  color: 'text.disabled',
  flexShrink: 0,
};

export const faultClearedBy: SxProps<Theme> = {
  color: 'text.disabled',
  fontStyle: 'italic',
  ml: 'auto',
  whiteSpace: 'nowrap',
  flexShrink: 0,
};

export const faultPagination: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 1,
  mt: 1.5,
};

export const faultPageLabel: SxProps<Theme> = {
  color: 'text.secondary',
  fontSize: '0.7rem',
};

// ─── Skeleton helpers ──────────────────────────────────────────────────────

export const skeletonCentered: SxProps<Theme> = {
  mx: 'auto',
};

export const skeletonGaugeBar: SxProps<Theme> = {
  mb: 0.75,
  borderRadius: 2,
};

export const skeletonChartTitle: SxProps<Theme> = {
  mr: 1,
};

export const skeletonLegendChip: SxProps<Theme> = {
  borderRadius: 1,
};

export const skeletonFaultRow: SxProps<Theme> = {
  borderRadius: 0.75,
};

export const skeletonFaultCounter: SxProps<Theme> = {
  flex: '1 1 80px',
};

export const skeletonConsoleFlex: SxProps<Theme> = {
  flex: 1,
};

export const skeletonConsoleDarkTimestamp: SxProps<Theme> = {
  bgcolor: '#161b22',
  flexShrink: 0,
};

export const skeletonConsoleDarkLine: SxProps<Theme> = {
  bgcolor: '#161b22',
  flex: 1,
};
