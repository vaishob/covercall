import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface MockDataBadgeProps {
  isMockMode?: boolean;
  label?: string;
}

/**
 * Visible badge rendered next to hard-coded figures while mock mode is active
 * so mock values are never mistaken for computed solver output.
 */
export const MockDataBadge: React.FC<MockDataBadgeProps> = ({
  isMockMode = true,
  label = 'Mock data — not computed',
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  if (!isMockMode) return null;

  return (
    <Box
      component="span"
      data-testid="mock-data-badge"
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
      <ScienceOutlinedIcon sx={{ fontSize: 12 }} aria-hidden="true" />
      <Typography
        component="span"
        className="mono-tabular"
        sx={{
          fontSize: '0.68rem',
          fontWeight: 700,
          lineHeight: 1.2,
        }}
      >
        {label}
      </Typography>
    </Box>
  );
};
