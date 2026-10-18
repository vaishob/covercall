import React from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import SwapCallsOutlinedIcon from '@mui/icons-material/SwapCallsOutlined';
import TimerOffOutlinedIcon from '@mui/icons-material/TimerOffOutlined';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import HourglassEmptyOutlinedIcon from '@mui/icons-material/HourglassEmptyOutlined';
import type { LeadView, OfferView } from '../data/viewModel';
import { formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { ReplayBadge } from './ReplayBadge';

interface CascadeTimelineProps {
  view: LeadView;
}

/** Offers as the workflow sends them (§11.3 item 6): each reply window and the reply as it arrives. */
export const CascadeTimeline: React.FC<CascadeTimelineProps> = ({ view }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const meta = (status: OfferView['status']) => {
    switch (status) {
      case 'accepted':
        return { icon: <CheckCircleOutlineIcon sx={{ fontSize: 16 }} aria-hidden="true" />, bg: tokens.legalPassBg, fg: tokens.legalPassText, bd: tokens.legalPassBorder };
      case 'countered':
        return { icon: <SwapCallsOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />, bg: tokens.amberAlertBg, fg: tokens.amberAlertText, bd: tokens.amberAlertBorder };
      case 'decline':
      case 'withdrawn':
      case 'late':
        return { icon: <CancelOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />, bg: tokens.surfaceSubtle, fg: tokens.textSecondary, bd: tokens.borderStrong };
      case 'timeout':
        return { icon: <TimerOffOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />, bg: tokens.surfaceSubtle, fg: tokens.textSecondary, bd: tokens.borderStrong };
      case 'flagged':
        return { icon: <ShieldOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />, bg: tokens.ruleWarnBg, fg: tokens.ruleWarnText, bd: tokens.ruleWarnBorder };
      default:
        return { icon: <HourglassEmptyOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />, bg: tokens.amberAlertBg, fg: tokens.amberAlertText, bd: tokens.amberAlertBorder };
    }
  };

  return (
    <Paper component="section" aria-labelledby="timeline-heading" sx={{ p: 2, backgroundColor: tokens.surface }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 1.5 }}>
        <Typography id="timeline-heading" variant="h2" component="h2">
          Outreach cascade
        </Typography>
        <ReplayBadge show={view.source === 'replay'} />
      </Box>

      {view.quarantine.map((q) => (
        <Box key={q.id} role="alert" sx={{ p: 1.5, mb: 2, borderRadius: 2, backgroundColor: tokens.ruleWarnBg, color: tokens.ruleWarnText, border: `1.5px solid ${tokens.ruleWarnBorder}` }}>
          <Typography sx={{ fontSize: '0.85rem', fontWeight: 700 }}>
            Quarantined for your review ({q.guardImpl ?? 'guard'}) · {q.guardLabels.join(', ')}
          </Typography>
          <Typography className="mono-tabular" sx={{ fontSize: '0.82rem', mt: 0.5 }}>
            From {q.staffName}: &ldquo;{q.redactedText}&rdquo;
          </Typography>
          <Typography sx={{ fontSize: '0.78rem' }}>Never shown to the planner; that candidate was skipped.</Typography>
        </Box>
      ))}

      {view.offers.length === 0 ? (
        <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
          No offers yet. Nothing is sent to staff before you approve the plan.
        </Typography>
      ) : (
        <Box component="ol" sx={{ listStyle: 'none', p: 0, m: 0, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          {view.offers.map((offer) => {
            const m = meta(offer.status);
            return (
              <Box component="li" key={offer.offerId} data-testid="offer" sx={{ p: 1.25, borderRadius: 2, backgroundColor: tokens.surfaceSubtle, border: `1px solid ${tokens.borderSubtle}` }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                  <Typography sx={{ fontWeight: 700, fontSize: '0.9rem' }}>
                    Offer {offer.seq}: {offer.staffName}{' '}
                    <span className="mono-tabular" style={{ fontWeight: 500 }}>
                      {formatTime12h(offer.start)}–{formatTime12h(offer.end)}
                    </span>
                  </Typography>
                  <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.35, borderRadius: 1.5, backgroundColor: m.bg, color: m.fg, border: `1px solid ${m.bd}` }}>
                    {m.icon}
                    <Typography component="span" sx={{ fontSize: '0.74rem', fontWeight: 700 }}>
                      {offer.statusLabel}
                    </Typography>
                  </Box>
                </Box>
                <Typography variant="caption" className="mono-tabular" sx={{ display: 'block', color: tokens.textMuted, mt: 0.5 }}>
                  Sent {formatTime12h(offer.sentAt)} · reply window {Math.round(offer.windowS / 60)} min
                  {offer.round?.startsWith('fanout') ? ' · fan-out (first yes wins)' : ''}
                  {offer.lateReply ? ' · late reply got a courtesy message' : ''}
                </Typography>
              </Box>
            );
          })}
        </Box>
      )}
    </Paper>
  );
};
