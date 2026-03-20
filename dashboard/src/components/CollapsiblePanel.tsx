import { useState, useEffect, useRef } from 'preact/hooks';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import type { CollapsiblePanelProps } from '../types/components';
import * as sx from '../theme/styles';

// ─── Component ────────────────────────────────────────────────────────────────

export function CollapsiblePanel({ title, defaultExpanded = true, expanded: controlledExpanded, children }: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultExpanded);
  const prevControlled = useRef(controlledExpanded);

  useEffect(() => {
    if (controlledExpanded !== undefined && controlledExpanded !== prevControlled.current) {
      setOpen(controlledExpanded);
    }
    prevControlled.current = controlledExpanded;
  }, [controlledExpanded]);

  return (
    <Box sx={sx.card}>
      {/* ── Clickable header bar ──────────────────────────────────────────── */}
      <Box onClick={() => setOpen((v) => !v)} sx={sx.collapsibleHeader}>
        <Typography variant="subtitle2" sx={sx.panelTitle}>
          {title}
        </Typography>
        <IconButton size="small" sx={sx.collapsibleToggle}>
          {open ? '▲' : '▼'}
        </IconButton>
      </Box>

      {/* ── Collapsible body ─────────────────────────────────────────────── */}
      {open && (
        <Box sx={sx.collapsibleBody}>
          {children}
        </Box>
      )}
    </Box>
  );
}
