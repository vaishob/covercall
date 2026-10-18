import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface ReplayBadgeProps {
  show: boolean;
  label?: string;
}

/**
 * Shown next to figures while the app plays a recorded replay (VITE_API_BASE_URL unset), so a
 * recording is never mistaken for a live run. Live mode shows no badge.
 */
export const ReplayBadge: React.FC<ReplayBadgeProps> = ({ show, label = 'Recorded replay — not live' }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  if (!show) return null;
  return (
    <Box
      component="span"
      data-testid="replay-badge"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.4,
        px: 0.75,
        py: 0.2,
        borderRadius: 1,
        backgroundColor: tokens.amberAlertBg,
        color: tokens.amberAlertText,
        border: `1px solid ${tokens.amberAlertBorder}`,
        verticalAlign: 'middle',
      }}
    >
      <HistoryOutlinedIcon sx={{ fontSize: 12 }} aria-hidden="true" />
      <Typography component="span" className="mono-tabular" sx={{ fontSize: '0.68rem', fontWeight: 700, lineHeight: 1.2 }}>
        {label}
      </Typography>
    </Box>
  );
};
