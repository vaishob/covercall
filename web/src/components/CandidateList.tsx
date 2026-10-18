import React from 'react';
import { Box, Paper, Typography, useTheme } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import DirectionsTransitOutlinedIcon from '@mui/icons-material/DirectionsTransitOutlined';
import SwapHorizOutlinedIcon from '@mui/icons-material/SwapHorizOutlined';
import type { LeadView, PlanOptionView } from '../data/viewModel';
import { centsToSgd } from '../data/viewModel';
import { formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { RuleWarningCard } from './RuleWarningCard';
import { ReplayBadge } from './ReplayBadge';

interface CandidateListProps {
  view: LeadView;
}

function savingText(plan: PlanOptionView, naive: LeadView['naive']): string | null {
  if (plan.savesVsNaiveCents === null || !naive) return null;
  const amount = centsToSgd(Math.abs(plan.savesVsNaiveCents));
  if (plan.savesVsNaiveCents === 0) return `Same overtime as the usual first pick (${naive.name})`;
  return plan.savesVsNaiveCents > 0
    ? `${amount} less overtime than the usual first pick (${naive.name})`
    : `${amount} more overtime than the usual first pick (${naive.name})`;
}

/** Ranked plans (§11.3 item 4) and greyed-out candidates with rule warnings (§11.4). */
export const CandidateList: React.FC<CandidateListProps> = ({ view }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const isReplay = view.source === 'replay';

  return (
    <Box component="section" aria-labelledby="plans-heading" sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
        <Typography id="plans-heading" variant="h2" component="h2">
          Ranked legal plans ({view.plans.length})
        </Typography>
        <ReplayBadge show={isReplay} />
      </Box>
      {view.plans.length === 0 && (
        <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
          {view.gap.state === 'REPORTED' || view.gap.state === 'GUARDED'
            ? 'Solving…'
            : 'No legal plan right now.'}
        </Typography>
      )}
      {view.naive && view.naive.blockingRuleIds.length > 0 && (
        <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
          The usual first pick, {view.naive.name}, would break {view.naive.blockingRuleIds.join(', ')}. Savings
          below compare overtime cost with that pick, at synthetic wages.
        </Typography>
      )}

      {view.plans.map((plan) => {
        const saving = savingText(plan, view.naive);
        const names = plan.segments.map((s) => s.name).join(' + ');
        return (
          <Paper
            key={plan.rank}
            component="article"
            data-testid="plan-option"
            aria-label={`Plan ${plan.rank}: ${names}`}
            sx={{ p: 2, backgroundColor: tokens.surface, borderWidth: plan.rank === 1 ? 2 : 1, borderColor: plan.rank === 1 ? tokens.brandPrimary : tokens.borderSubtle }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.5, mb: 1 }}>
              <Box>
                <Typography component="span" className="mono-tabular" sx={{ fontSize: '0.8rem', fontWeight: 700, color: tokens.brandPrimary }}>
                  #{plan.rank}
                  {plan.rank === 1 ? ' · Top pick' : ''}
                  {plan.isSplit ? ' · Split shift' : ''}
                </Typography>
                <Typography variant="h3" component="h3" sx={{ fontWeight: 700 }}>
                  {names}
                </Typography>
              </Box>
              <Box sx={{ textAlign: { xs: 'left', sm: 'right' } }}>
                <Typography className="mono-tabular" sx={{ fontWeight: 700 }}>
                  Overtime {centsToSgd(plan.overtimeCents)} · Total {centsToSgd(plan.totalCents)}
                </Typography>
                {saving && (
                  <Typography className="mono-tabular" sx={{ fontSize: '0.85rem', color: tokens.legalPassText, fontWeight: 600 }}>
                    {saving}
                  </Typography>
                )}
                <Typography variant="caption" sx={{ color: tokens.textMuted, display: 'block' }}>
                  Synthetic wages; not a claim about real money.
                </Typography>
              </Box>
            </Box>

            {plan.segments.map((seg) => (
              <Box
                key={`${seg.staffId}-${seg.start}`}
                sx={{ p: 1.25, mb: 1, borderRadius: 1.5, backgroundColor: tokens.surfaceSubtle, display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', justifyContent: 'space-between' }}
              >
                <Box>
                  <Typography sx={{ fontWeight: 700, fontSize: '0.92rem' }}>
                    {seg.name}{' '}
                    <span className="mono-tabular" style={{ fontWeight: 500 }}>
                      {formatTime12h(seg.start)}–{formatTime12h(seg.end)}
                    </span>
                  </Typography>
                  <Typography variant="caption" sx={{ color: tokens.textSecondary }}>
                    {seg.homeOutlet !== view.gap.outlet ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <SwapHorizOutlinedIcon sx={{ fontSize: 14 }} aria-hidden="true" /> Borrowed from {seg.homeOutlet}
                      </span>
                    ) : (
                      `Home outlet ${seg.homeOutlet}`
                    )}
                    {seg.breaks.length > 0 &&
                      ` · Break ${seg.breaks.map((b) => `${formatTime12h(b.start)} (${b.durationMin} min)`).join(', ')}`}
                  </Typography>
                </Box>
                <Typography className="mono-tabular" sx={{ fontSize: '0.85rem', display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                  <DirectionsTransitOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />
                  {seg.travelMin} min travel · could arrive {formatTime12h(seg.arrival)}
                </Typography>
              </Box>
            ))}

            <Box aria-label={`Rule checks for plan ${plan.rank}`} sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
              {plan.passedChecks.map((r) => (
                <Box
                  component="span"
                  key={`${r.staffName}-${r.ruleId}`}
                  title={`${r.staffName}: ${r.title} (${r.kindLabel}) passed`}
                  sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.35, borderRadius: 1.5, backgroundColor: tokens.legalPassBg, color: tokens.legalPassText, border: `1px solid ${tokens.legalPassBorder}`, fontSize: '0.72rem', fontWeight: 600 }}
                >
                  <CheckCircleOutlineIcon sx={{ fontSize: 14 }} aria-hidden="true" />
                  <span className="mono-tabular">
                    {plan.isSplit ? `${r.staffName}: ` : ''}
                    {r.ruleId} passed
                  </span>
                </Box>
              ))}
            </Box>
          </Paper>
        );
      })}

      <Box sx={{ mt: 1 }}>
        <Typography variant="h2" component="h2" sx={{ mb: 0.5 }}>
          Not offered: rule warnings ({view.rejected.length})
        </Typography>
        <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 1.5 }}>
          Each warning comes from the rule spec with numbers computed by the validator. A language model never decides legality.
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {view.rejected.map((r) => (
            <RuleWarningCard key={r.key} rejected={r} isReplay={isReplay} />
          ))}
        </Box>
      </Box>
    </Box>
  );
};
