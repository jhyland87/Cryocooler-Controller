import { useState, useEffect, useRef } from 'preact/hooks';
import type { ComponentChildren } from 'preact';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';

// ─── Public API ───────────────────────────────────────────────────────────────

interface Props {
  /** Panel heading shown in the collapse bar. */
  title: string;
  /** Whether the panel starts expanded. Default: true */
  defaultExpanded?: boolean;
  /** Controlled expanded state — overrides internal state when it changes. */
  expanded?: boolean;
  children: ComponentChildren;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function CollapsiblePanel({ title, defaultExpanded = true, expanded: controlledExpanded, children }: Props) {
  const [open, setOpen] = useState(defaultExpanded);
  const prevControlled = useRef(controlledExpanded);

  // React to controlled `expanded` prop changes (e.g. faults appearing).
  useEffect(() => {
    if (controlledExpanded !== undefined && controlledExpanded !== prevControlled.current) {
      setOpen(controlledExpanded);
    }
    prevControlled.current = controlledExpanded;
  }, [controlledExpanded]);

  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        borderRadius: 1,
        border: '1px solid',
        borderColor: 'divider',
        overflow: 'hidden',
      }}
    >
      {/* ── Clickable header bar ──────────────────────────────────────────── */}
      <Box
        onClick={() => setOpen((v) => !v)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.75,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: 'action.hover' },
        }}
      >
        <Typography
          variant="subtitle2"
          sx={{
            color: 'text.secondary',
            fontWeight: 600,
            letterSpacing: 1,
            textTransform: 'uppercase',
            fontSize: '0.7rem',
          }}
        >
          {title}
        </Typography>
        <IconButton size="small" sx={{ p: 0.25, color: 'text.disabled', fontSize: '0.85rem' }}>
          {open ? '▲' : '▼'}
        </IconButton>
      </Box>

      {/* ── Collapsible body ─────────────────────────────────────────────── */}
      {open && (
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          {children}
        </Box>
      )}
    </Box>
  );
}
