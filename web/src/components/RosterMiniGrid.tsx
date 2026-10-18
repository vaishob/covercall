import React from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import type { LeadView } from '../data/viewModel';
import { formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { ReplayBadge } from './ReplayBadge';

interface RosterMiniGridProps {
  view: LeadView;
}

/** The gap's hours and who covers each one: the committed plan, or else the top-ranked plan. */
export const RosterMiniGrid: React.FC<RosterMiniGridProps> = ({ view }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const label = view.committed ? 'Committed cover' : 'Top-ranked plan (not yet committed)';
  return (
    <Paper component="section" aria-labelledby="roster-heading" sx={{ p: 2, backgroundColor: tokens.surface }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 0.5 }}>
        <Typography id="roster-heading" variant="h2" component="h2">
          Roster: {view.roster.label}
        </Typography>
        <ReplayBadge show={view.source === 'replay'} />
      </Box>
      <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 1 }}>
        {label}
      </Typography>
      {/* Keyboard users must be able to scroll this region (WCAG 2.1.1; axe scrollable-region-focusable). */}
      <Box
        tabIndex={0}
        role="region"
        aria-label="Roster hours (scrolls sideways)"
        sx={{ overflowX: 'auto', '&:focus-visible': { outline: `3px solid ${tokens.brandPrimary}`, outlineOffset: 2 } }}
      >
        <Box component="table" sx={{ borderCollapse: 'collapse', width: '100%' }} aria-label="Who covers each hour">
          <thead>
            <tr>
              {view.roster.cells.map((c) => (
                <Box component="th" scope="col" key={c.hour} sx={{ p: 0.5, fontSize: '0.72rem', textAlign: 'center' }}>
                  {formatTime12h(c.hour)}
                </Box>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {view.roster.cells.map((c) => (
                <Box
                  component="td"
                  key={c.hour}
                  sx={{
                    p: 0.75,
                    fontSize: '0.75rem',
                    textAlign: 'center',
                    border: `1px solid ${tokens.borderSubtle}`,
                    backgroundColor: c.staffName ? tokens.legalPassBg : tokens.surfaceSubtle,
                    color: c.staffName ? tokens.legalPassText : tokens.textSecondary,
                  }}
                >
                  {c.staffName ?? 'gap'}
                </Box>
              ))}
            </tr>
          </tbody>
        </Box>
      </Box>
    </Paper>
  );
};
