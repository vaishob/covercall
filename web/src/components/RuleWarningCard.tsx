import React from 'react';
import { Box, Link, Paper, Typography, useTheme } from '@mui/material';
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import type { RejectedView } from '../data/viewModel';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { ReplayBadge } from './ReplayBadge';

interface RuleWarningCardProps {
  rejected: RejectedView;
  isReplay: boolean;
}

/**
 * §11.4 RuleWarning: icon plus text label (never colour alone), staff name, the spec's message
 * with computed numbers, the rule ID, and a link to the rule's own source (from the data).
 */
export const RuleWarningCard: React.FC<RuleWarningCardProps> = ({ rejected, isReplay }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  return (
    <Paper
      component="article"
      data-testid="rule-warning"
      aria-label={`Not offered: ${rejected.name}, ${rejected.ruleId}`}
      sx={{ p: 2, backgroundColor: tokens.surfaceMutedRejected, borderColor: tokens.borderSubtle }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1, mb: 1 }}>
        <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.4, borderRadius: 1.5, backgroundColor: tokens.ruleWarnBg, color: tokens.ruleWarnText, border: `1px solid ${tokens.ruleWarnBorder}` }}>
          <BlockOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
          <Typography component="span" sx={{ fontSize: '0.76rem', fontWeight: 700 }}>
            Blocked · {rejected.kindLabel}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ReplayBadge show={isReplay} />
          <Typography variant="caption" className="mono-tabular" sx={{ color: tokens.textMuted }}>
            {rejected.homeOutlet ?? ''} · {rejected.staffId}
          </Typography>
        </Box>
      </Box>
      <Typography sx={{ fontSize: '0.95rem', lineHeight: 1.5, mb: 0.75 }}>{rejected.message}</Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1, pt: 1, borderTop: `1px solid ${tokens.borderSubtle}` }}>
        <Typography component="span" className="mono-tabular" sx={{ fontSize: '0.8rem', fontWeight: 700, color: tokens.ruleWarnText }}>
          {rejected.ruleId} · {rejected.title}
        </Typography>
        <Link
          href={rejected.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${rejected.ruleId} source: ${rejected.publisher}, ${rejected.section}`}
          sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, fontSize: '0.8rem', minHeight: 48, px: 1 }}
        >
          <span>
            {rejected.publisher} · {rejected.section}
          </span>
          <OpenInNewIcon sx={{ fontSize: 14 }} aria-hidden="true" />
        </Link>
      </Box>
    </Paper>
  );
};
