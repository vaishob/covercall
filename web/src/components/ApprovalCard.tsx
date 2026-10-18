import React from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import VolumeUpOutlinedIcon from '@mui/icons-material/VolumeUpOutlined';
import type { LeadView } from '../data/viewModel';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';

interface ApprovalCardProps {
  view: LeadView;
  canAct: boolean;
  busy: boolean;
  onDecide: (decision: 'approve' | 'reject') => void;
  onChooseFallback: (option: string) => void;
}

/**
 * §11.3 item 7 and §5.3: sticky approval card with the exact read-back sentence from the server
 * (GET /gaps/{id}/approval). In ESCALATED it shows the ranked fallbacks instead.
 */
export const ApprovalCard: React.FC<ApprovalCardProps> = ({ view, canAct, busy, onDecide, onChooseFallback }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const escalated = view.gap.state === 'ESCALATED';
  if (!view.approval && !escalated) return null;

  return (
    <Paper
      component="section"
      aria-labelledby="approval-heading"
      sx={{ position: 'sticky', bottom: 0, zIndex: 25, p: 1.5, borderRadius: '12px 12px 0 0', backgroundColor: tokens.surfaceElevated, borderTop: `2px solid ${tokens.brandPrimary}` }}
    >
      {escalated ? (
        <>
          <Typography id="approval-heading" sx={{ fontWeight: 700, mb: 0.75, color: tokens.ruleWarnText }}>
            Nobody accepted in time. Choose a fallback:
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 0.75 }}>
            {view.gap.fallbacks.map((f, i) => (
              <Button key={f.id} variant={i === 0 ? 'contained' : 'outlined'} disabled={!canAct || busy} onClick={() => onChooseFallback(f.id)} sx={{ minHeight: 48 }}>
                {i + 1}. {f.label}
              </Button>
            ))}
          </Box>
        </>
      ) : (
        view.approval && (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 0.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <VolumeUpOutlinedIcon sx={{ fontSize: 16, color: tokens.brandPrimary }} aria-hidden="true" />
                <Typography id="approval-heading" sx={{ fontSize: '0.8rem', fontWeight: 700 }}>
                  Tier T2 approval: CoverCall will message staff only after you say yes
                </Typography>
              </Box>
              <Typography variant="caption" className="mono-tabular" sx={{ color: tokens.textMuted }}>
                nonce {view.approval.nonce}
              </Typography>
            </Box>
            <Typography data-testid="readback" sx={{ fontSize: '0.86rem', fontWeight: 600, lineHeight: 1.4, mb: 1 }}>
              &ldquo;{view.approval.readback}&rdquo;
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1.25fr 1fr', gap: 1 }}>
              <Button variant="contained" disabled={!canAct || busy} onClick={() => onDecide('approve')} sx={{ minHeight: 48, fontWeight: 700 }}>
                <CheckIcon sx={{ mr: 0.5, fontSize: 18 }} aria-hidden="true" />
                Approve plan
              </Button>
              <Button variant="outlined" disabled={!canAct || busy} onClick={() => onDecide('reject')} sx={{ minHeight: 48 }}>
                <CloseIcon sx={{ mr: 0.5, fontSize: 18 }} aria-hidden="true" />
                Reject
              </Button>
            </Box>
          </>
        )
      )}
      {!canAct && (
        <Typography variant="caption" sx={{ display: 'block', mt: 0.75, color: tokens.amberAlertText }}>
          Recorded replay: these buttons are disabled.
        </Typography>
      )}
    </Paper>
  );
};
