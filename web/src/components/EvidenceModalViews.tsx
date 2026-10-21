import React, { useEffect, useState } from 'react';
import { Box, Button, Paper, Typography, useTheme } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import type { EvalsDto, ScenarioDto, StatusDto } from '../data/backendTypes';
import type { LeadSource } from '../data/source';
import type { TraceView } from '../data/viewModel';
import { formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { ReplayBadge } from './ReplayBadge';

export type Route = '/' | '/evals' | '/trace' | '/about';

interface EvidenceViewsProps {
  activeRoute: Exclude<Route, '/'>;
  gapHandle: string | null;
  source: LeadSource;
  scenarios: ScenarioDto[];
  onNavigate: (route: Route) => void;
}

/** P0 metric definitions from §10.1 (text only; values come from the release gate in Slice 6). */
/** What the implementation ID reported by /status means; `provider` is that role's entry in /status models. */
function implNote(impl: string, provider: string | undefined): string {
  if (impl.startsWith('stub')) return 'deterministic stub, not a model';
  return provider === 'gemini_developer_api'
    ? 'Gemini model on the Gemini Developer API; fails closed'
    : 'Gemini model on the Enterprise Agent Platform, global endpoint; fails closed';
}

const P0_DEFINITIONS: Array<[string, string]> = [
  ['rule_violations', 'Proposed or committed assignments that fail the validator'],
  ['solver_validator_disagreements', 'Cases where the solver and validator disagree'],
  ['unapproved_outbound', 'Staff-facing messages sent without a covering T2 approval'],
  ['injection_executed', 'Adversarial replies that changed plan or state beyond quarantine'],
  ['pii_leak', 'Unredacted PII patterns found in events, logs, traces or BigQuery'],
  ['outcome_missing', 'Gaps that ended without a recorded terminal outcome'],
  ['escalation_late', 'Escalations that fired after t_esc'],
  ['nondeterminism', 'Same scenario and seed producing a different ranking'],
];

export const EvidenceViews: React.FC<EvidenceViewsProps> = ({ activeRoute, gapHandle, source, scenarios, onNavigate }) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;
  const [evals, setEvals] = useState<EvalsDto | null>(null);
  const [status, setStatus] = useState<StatusDto | null>(null);
  const [trace, setTrace] = useState<TraceView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isReplay = source.kind === 'replay';

  useEffect(() => {
    setError(null);
    if (activeRoute === '/evals') source.evals().then(setEvals, (e: Error) => setError(e.message));
    if (activeRoute === '/about') source.status().then(setStatus, (e: Error) => setError(e.message));
    if (activeRoute === '/trace' && gapHandle) source.trace(gapHandle).then(setTrace, (e: Error) => setError(e.message));
  }, [activeRoute, gapHandle, source]);

  const tab = (route: Exclude<Route, '/'>, label: string) => (
    <Button variant={activeRoute === route ? 'contained' : 'outlined'} onClick={() => onNavigate(route)} sx={{ minHeight: 48, fontSize: '0.82rem' }}>
      {label}
    </Button>
  );

  return (
    <Box component="section" sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
        <Button variant="outlined" onClick={() => onNavigate('/')} sx={{ minHeight: 48, fontWeight: 700 }}>
          <ArrowBackIcon sx={{ fontSize: 18, mr: 0.75 }} aria-hidden="true" />
          Back to lead view
        </Button>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {tab('/evals', '/evals')}
          {gapHandle && tab('/trace', `/trace/${gapHandle}`)}
          {tab('/about', '/about')}
        </Box>
      </Box>

      {error && (
        <Paper role="alert" sx={{ p: 2, backgroundColor: tokens.ruleWarnBg, color: tokens.ruleWarnText }}>
          {error}
        </Paper>
      )}

      {activeRoute === '/evals' && evals && (
        <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
          <Typography variant="h1" component="h1">
            Release gate and evaluation (/evals)
          </Typography>
          <Box data-testid="release-gate-badge" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, my: 1.5, px: 1.5, py: 0.75, borderRadius: 2, backgroundColor: tokens.amberAlertBg, color: tokens.amberAlertText, border: `1.5px solid ${tokens.amberAlertBorder}` }}>
            <WarningAmberOutlinedIcon sx={{ fontSize: 18 }} aria-hidden="true" />
            <Typography sx={{ fontWeight: 700 }}>{evals.status === 'no_eval_run' ? 'No eval run yet' : evals.status}</Typography>
          </Box>
          <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 2 }}>
            {evals.message}
          </Typography>
          <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
            P0 release-blocking counters (pass rule: exactly 0)
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {P0_DEFINITIONS.map(([metric, def]) => (
              <li key={metric}>
                <span className="mono-tabular" style={{ fontWeight: 700 }}>{metric}</span>: {def}. Value: no eval run yet.
              </li>
            ))}
          </Box>
        </Paper>
      )}

      {activeRoute === '/trace' && (
        <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AccountTreeOutlinedIcon sx={{ color: tokens.brandPrimary }} aria-hidden="true" />
              <Typography variant="h1" component="h1">
                Trace replay {gapHandle ? `(${gapHandle})` : ''}
              </Typography>
              <ReplayBadge show={isReplay} />
            </Box>
            {trace && (
              <Box data-testid="chain-verification-status" sx={{ px: 1.25, py: 0.5, borderRadius: 1.5, backgroundColor: trace.chainOk ? tokens.legalPassBg : tokens.ruleWarnBg, color: trace.chainOk ? tokens.legalPassText : tokens.ruleWarnText, border: `1px solid ${trace.chainOk ? tokens.legalPassBorder : tokens.ruleWarnBorder}`, display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                {trace.chainOk ? <VerifiedUserOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" /> : <WarningAmberOutlinedIcon sx={{ fontSize: 16 }} aria-hidden="true" />}
                <Typography className="mono-tabular" sx={{ fontSize: '0.78rem', fontWeight: 700 }}>
                  {trace.chainOk ? `Hash chain verified by the server (${trace.events.length} events)` : `Hash chain broken: ${trace.chainErrors.join('; ')}`}
                </Typography>
              </Box>
            )}
          </Box>
          {!gapHandle && <Typography>Start a scenario first.</Typography>}
          <Box component="ol" sx={{ listStyle: 'none', p: 0, m: 0, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            {(trace?.events ?? []).map((ev) => (
              <Box component="li" key={ev.seq} sx={{ p: 1.5, borderRadius: 2, backgroundColor: tokens.surfaceSubtle, border: `1px solid ${tokens.borderSubtle}` }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                  <Typography className="mono-tabular" sx={{ fontSize: '0.84rem', fontWeight: 700 }}>
                    #{ev.seq} {ev.type} ({ev.from} → {ev.to})
                  </Typography>
                  <Typography variant="caption" className="mono-tabular" sx={{ color: tokens.textMuted }}>
                    {formatTime12h(ev.ts)} · actor {ev.actor}
                  </Typography>
                </Box>
                {ev.payloadSummary && <Typography variant="body2">{ev.payloadSummary}</Typography>}
                <Typography variant="caption" className="mono-tabular" sx={{ color: tokens.textSecondary, display: 'block', overflowWrap: 'anywhere' }}>
                  rule_ids [{ev.ruleIds.join(', ')}] · hash {ev.hash.slice(0, 16)}… · prev {ev.prevHash.slice(0, 16)}…
                </Typography>
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {activeRoute === '/about' && (
        <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
          <Typography variant="h1" component="h1" sx={{ mb: 1 }}>
            About CoverCall
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            A shift lead at a small three-outlet café chain in Singapore gets a sick call before opening. CoverCall finds legal,
            low-cost cover, messages candidates after the lead approves, re-plans on declines and counter-offers, and escalates
            when time runs out. Every assignment is checked by a constraint solver and an independent validator, never by a
            language model.
          </Typography>
          <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
            Scenarios
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5, mb: 2 }}>
            {scenarios.map((s) => (
              <li key={s.scenario_id}>
                <strong>{s.label}</strong> ({s.scenario_id}, {s.journey}): {s.description}
              </li>
            ))}
          </Box>
          <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
            Components and model IDs (from GET /status)
          </Typography>
          {status && (
            <Box component="ul" sx={{ m: 0, pl: 2.5, mb: 2 }} className="mono-tabular">
              <li>guard: {status.guard_impl} (deterministic stub, not a model)</li>
              <li>reply parser: {status.parser_impl} ({implNote(status.parser_impl, status.models.agent?.provider)})</li>
              <li>
                persona reply text: {status.persona_text_impl} (
                {implNote(status.persona_text_impl, status.models.persona_sim?.provider)})
              </li>
              <li>
                voice: {status.voice === 'live'
                  ? 'live (Gemini Live, v1beta single-use ephemeral tokens minted by api; tools run on the server)'
                  : 'off on this deployment (scenario buttons and text only)'}
              </li>
              {Object.entries(status.models).map(([role, m]) => (
                <li key={role}>
                  {role}: {m.model_id} ({m.api_version})
                </li>
              ))}
            </Box>
          )}
          <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
            All data is synthetic. Each rule warning links to that rule&apos;s own public source (MOM or SFA), taken from
            the rule spec.
          </Typography>
        </Paper>
      )}
    </Box>
  );
};
