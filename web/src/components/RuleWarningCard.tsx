import React from 'react';
import { Box, Link, Paper, Typography, useTheme } from '@mui/material';
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { RejectedCandidate } from '../mocks/state';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { MockDataBadge } from './MockDataBadge';

interface RuleWarningCardProps {
  rejected: RejectedCandidate;
  isMockMode?: boolean;
}

/**
 * §11.4 RuleWarning anatomy:
 * - Severity icon plus a text label, never colour alone.
 * - Staff name, then the plain-English message from the rule spec with computed numbers.
 * - Rule ID and a link to its source (MOM hours/overtime/rest-day page or data-supplied URL).
 */
export const RuleWarningCard: React.FC<RuleWarningCardProps> = ({
  rejected,
  isMockMode = true,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  return (
    <Paper
      component="article"
      aria-label={`Rejected candidate ${rejected.display_name}: ${rejected.rule_id}`}
      sx={{
        p: 2,
        backgroundColor: tokens.surfaceMutedRejected,
        borderColor: tokens.borderSubtle,
        opacity: 0.94,
      }}
    >
      {/* Top Row: Severity icon + text label (never colour alone) + Mock Badge + Home Outlet */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1,
          mb: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.75,
              px: 1,
              py: 0.4,
              borderRadius: 1.5,
              backgroundColor: tokens.ruleWarnBg,
              color: tokens.ruleWarnText,
              border: `1px solid ${tokens.ruleWarnBorder}`,
            }}
          >
            <BlockOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
            <Typography
              component="span"
              sx={{ fontSize: '0.76rem', fontWeight: 700 }}
            >
              Blocked · {rejected.severity}
            </Typography>
          </Box>
          <MockDataBadge isMockMode={isMockMode || rejected.is_mock} />
        </Box>

        <Typography
          variant="caption"
          className="mono-tabular"
          sx={{ color: tokens.textMuted }}
        >
          {rejected.home_outlet} · {rejected.staff_id}
        </Typography>
      </Box>

      {/* Main Plain-English Rule Warning Line (§11.4 exact anatomy) */}
      <Typography
        sx={{
          fontSize: '0.95rem',
          lineHeight: 1.5,
          color: tokens.textPrimary,
          mb: 0.75,
        }}
      >
        <strong>{rejected.display_name}:</strong> {rejected.plain_english_message}
      </Typography>

      <Typography
        variant="caption"
        sx={{ display: 'block', color: tokens.textSecondary, mb: 1 }}
      >
        Context: {rejected.role_note}
      </Typography>

      {/* Bottom Row: Canonical Rule ID + Cited Public Source Link */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1,
          pt: 1,
          borderTop: `1px solid ${tokens.borderSubtle}`,
        }}
      >
        <Typography
          component="span"
          className="mono-tabular"
          sx={{
            fontSize: '0.8rem',
            fontWeight: 700,
            color: tokens.ruleWarnText,
          }}
        >
          {rejected.rule_id}
        </Typography>

        <Link
          href={rejected.source.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${rejected.rule_id} ${rejected.source.publisher} source: ${rejected.source.title} (${rejected.source.section})`}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            fontSize: '0.8rem',
            minHeight: 48,
            px: 1,
          }}
        >
          <span>
            {rejected.source.publisher} source ({rejected.source.section})
          </span>
          <OpenInNewIcon sx={{ fontSize: 14 }} aria-hidden="true" />
        </Link>
      </Box>
    </Paper>
  );
};
