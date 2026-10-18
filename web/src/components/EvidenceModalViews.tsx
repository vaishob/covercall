import React, { useEffect, useState } from 'react';
import { Box, Button, Link, Paper, Typography, useTheme } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { MOM_HOURS_OVERTIME_REST_URL, SCENARIO_DESCRIPTORS } from '../mocks/state';
import type { DataSource } from '../data/dataSource';
import type { CoverCallEvalsReadModel, GapEventDoc } from '../data/types';
import { formatCurrencySGD, formatTime12h } from '../utils/formatters';
import { DARK_TOKENS, LIGHT_TOKENS } from '../theme';
import { MockDataBadge } from './MockDataBadge';

interface EvidenceViewsProps {
  activeRoute: '/evals' | '/trace' | '/about';
  gapId: string;
  workflowExecutionId: string;
  dataSource: DataSource;
  isMockMode?: boolean;
  onBackToLeadView: () => void;
  onNavigateRoute: (route: '/' | '/evals' | '/trace' | '/about', targetGapId?: string) => void;
}

const P0_DEFINITIONS: Record<string, string> = {
  rule_violations: 'Proposed or committed assignments that fail the validator, golden and held-out sets',
  solver_validator_disagreements: 'Cases where the solver and validator disagree, including property tests',
  unapproved_outbound: 'Staff-facing messages sent without a covering T2 approval',
  injection_executed: 'Adversarial replies that changed plan or state beyond quarantine',
  pii_leak: 'Unredacted PII patterns found in events, logs, traces or BigQuery',
  outcome_missing: 'Gaps that ended without a recorded terminal outcome',
  escalation_late: 'Escalations that fired after t_esc',
  nondeterminism: 'Same scenario and seed producing a different ranking',
};

const P1_DEFINITIONS: Record<string, string> = {
  overtime_saved_sgd: 'Median and total, CoverCall against the baseline',
  cost_gap_vs_optimum: 'Median % above the offline optimum',
  time_to_fill_min: 'Median simulated minutes from report to fill',
  parse_accuracy: 'Intent accuracy per language slice',
  guard_precision_recall: 'Per label and per language slice, Gemma and Gemini baseline side by side',
  voice_slot_accuracy: 'Outlet, time, station and name extracted correctly from recorded lead speech',
};

const P2_DEFINITIONS: Record<string, string> = {
  message_quality: 'Gemini Pro judge score, 1 to 5 per criterion (§7.5)',
  latency_p95: 'Per service and per model call',
};

export const EvidenceViews: React.FC<EvidenceViewsProps> = ({
  activeRoute,
  gapId,
  workflowExecutionId,
  dataSource,
  isMockMode = true,
  onBackToLeadView,
  onNavigateRoute,
}) => {
  const theme = useTheme();
  const tokens = theme.palette.mode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const [evalsModel, setEvalsModel] = useState<CoverCallEvalsReadModel | null>(null);
  const [traceEvents, setTraceEvents] = useState<GapEventDoc[]>([]);
  const [chainVerified, setChainVerified] = useState<boolean | null>(null);
  const [p2Expanded, setP2Expanded] = useState<boolean>(false);

  useEffect(() => {
    void dataSource.getEvalsReadModel().then(setEvalsModel);
  }, [dataSource]);

  useEffect(() => {
    const unsub = dataSource.subscribeGapEvents(gapId, (events, verified) => {
      setTraceEvents(events);
      setChainVerified(verified);
    });
    return () => unsub();
  }, [dataSource, gapId]);

  const formatMetricVal = (val: number | null | undefined, suffix = ''): string => {
    if (val === null || val === undefined || isMockMode || evalsModel?.isMock) {
      return 'No eval run yet';
    }
    return `${val}${suffix}`;
  };

  return (
    <Box
      component="section"
      aria-label={
        activeRoute === '/evals'
          ? 'Release Gate and P0 Evaluation Evidence'
          : activeRoute === '/trace'
            ? 'Gap Event Hash Chain Trace Replay'
            : 'About CoverCall and Synthetic Data Notice'
      }
      sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
    >
      {/* Route Switcher Bar */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <Button
          variant="outlined"
          onClick={onBackToLeadView}
          sx={{ minHeight: 48, fontWeight: 700 }}
        >
          <ArrowBackIcon sx={{ fontSize: 18, mr: 0.75 }} aria-hidden="true" />
          Back to Lead View (/)
        </Button>

        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button
            variant={activeRoute === '/evals' ? 'contained' : 'outlined'}
            onClick={() => onNavigateRoute('/evals')}
            sx={{ minHeight: 48, fontSize: '0.82rem' }}
          >
            /evals
          </Button>
          <Button
            variant={activeRoute === '/trace' ? 'contained' : 'outlined'}
            onClick={() => onNavigateRoute('/trace', gapId)}
            sx={{ minHeight: 48, fontSize: '0.82rem' }}
          >
            /trace/{gapId}
          </Button>
          <Button
            variant={activeRoute === '/about' ? 'contained' : 'outlined'}
            onClick={() => onNavigateRoute('/about')}
            sx={{ minHeight: 48, fontSize: '0.82rem' }}
          >
            /about
          </Button>
        </Box>
      </Box>

      {/* ROUTE 1: /evals (§11.5) */}
      {activeRoute === '/evals' && evalsModel && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: '1.35fr 0.65fr' },
            gap: 2,
            alignItems: 'start',
          }}
        >
          {/* Main Column: Release Gate Badge, P0 Tiles, Baseline Headline, P1, Slice Tables, Collapsed P2 */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 1.5,
                  mb: 2,
                }}
              >
                <Box>
                  <Typography variant="h1" component="h1">
                    Release Gate &amp; Evaluation Suite (/evals)
                  </Typography>
                  <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
                    BigQuery dataset <code>covercall_evals</code> (§10.4, §11.5) · Tap any row to
                    open its trace replay
                  </Typography>
                </Box>

                {/* Release-gate badge (Passed, Blocked, or No eval run yet in mock mode) */}
                <Box
                  data-testid="release-gate-badge"
                  sx={{
                    px: 1.5,
                    py: 0.75,
                    borderRadius: 2,
                    backgroundColor: evalsModel.latestRun
                      ? evalsModel.latestRun.status === 'PASSED'
                        ? tokens.legalPassBg
                        : tokens.ruleWarnBg
                      : tokens.amberAlertBg,
                    color: evalsModel.latestRun
                      ? evalsModel.latestRun.status === 'PASSED'
                        ? tokens.legalPassText
                        : tokens.ruleWarnText
                      : tokens.amberAlertText,
                    border: `1.5px solid ${
                      evalsModel.latestRun
                        ? evalsModel.latestRun.status === 'PASSED'
                          ? tokens.legalPassBorder
                          : tokens.ruleWarnBorder
                        : tokens.amberAlertBorder
                    }`,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.75,
                  }}
                >
                  {evalsModel.latestRun?.status === 'PASSED' ? (
                    <VerifiedUserOutlinedIcon sx={{ fontSize: 18 }} aria-hidden="true" />
                  ) : (
                    <WarningAmberOutlinedIcon sx={{ fontSize: 18 }} aria-hidden="true" />
                  )}
                  <Typography className="mono-tabular" sx={{ fontSize: '0.82rem', fontWeight: 700 }}>
                    {evalsModel.latestRun
                      ? `Gate: ${evalsModel.latestRun.status} · Build ${evalsModel.latestRun.build_id} (${formatTime12h(
                          evalsModel.latestRun.started_at
                        )})`
                      : 'Release Gate: No eval run yet'}
                  </Typography>
                </Box>
              </Box>

              {/* Headline Results vs Naive Baseline (`baseline/most_reliable_first.py`) */}
              <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
                Headline Results vs Naive Baseline
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' },
                  gap: 1.5,
                  mb: 2,
                }}
              >
                <Box
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    backgroundColor: tokens.surfaceSubtle,
                    border: `1px solid ${tokens.borderSubtle}`,
                  }}
                >
                  <Typography variant="caption" sx={{ color: tokens.textSecondary, fontWeight: 700 }}>
                    Overtime Saved vs Baseline
                  </Typography>
                  <Typography
                    className="mono-tabular"
                    sx={{ fontSize: '1rem', fontWeight: 700, color: tokens.textPrimary, mt: 0.25 }}
                  >
                    {evalsModel.headlineVsBaseline.overtimeSavedMedianSgd !== null &&
                    !evalsModel.isMock
                      ? formatCurrencySGD(evalsModel.headlineVsBaseline.overtimeSavedMedianSgd)
                      : 'No eval run yet'}
                  </Typography>
                </Box>

                <Box
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    backgroundColor: tokens.surfaceSubtle,
                    border: `1px solid ${tokens.borderSubtle}`,
                  }}
                >
                  <Typography variant="caption" sx={{ color: tokens.textSecondary, fontWeight: 700 }}>
                    Rule Violations (CoverCall vs Baseline)
                  </Typography>
                  <Typography
                    className="mono-tabular"
                    sx={{ fontSize: '1rem', fontWeight: 700, color: tokens.textPrimary, mt: 0.25 }}
                  >
                    {evalsModel.headlineVsBaseline.coverCallViolations !== null && !evalsModel.isMock
                      ? `${evalsModel.headlineVsBaseline.coverCallViolations} vs ${evalsModel.headlineVsBaseline.baselineViolations}`
                      : 'No eval run yet'}
                  </Typography>
                </Box>

                <Box
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    backgroundColor: tokens.surfaceSubtle,
                    border: `1px solid ${tokens.borderSubtle}`,
                  }}
                >
                  <Typography variant="caption" sx={{ color: tokens.textSecondary, fontWeight: 700 }}>
                    Time to Fill (CoverCall vs Baseline)
                  </Typography>
                  <Typography
                    className="mono-tabular"
                    sx={{ fontSize: '1rem', fontWeight: 700, color: tokens.textPrimary, mt: 0.25 }}
                  >
                    {evalsModel.headlineVsBaseline.coverCallTimeToFillMin !== null &&
                    !evalsModel.isMock
                      ? `${evalsModel.headlineVsBaseline.coverCallTimeToFillMin}m vs ${evalsModel.headlineVsBaseline.baselineTimeToFillMin}m`
                      : 'No eval run yet'}
                  </Typography>
                </Box>
              </Box>

              {/* One Tile per P0 Metric (§10.1 & §11.5) */}
              <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
                P0 Release-Blocking Counters (Pass Rule: Exactly 0)
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
                  gap: 1.25,
                }}
              >
                {evalsModel.p0Metrics.map((m) => (
                  <Button
                    key={m.metric}
                    variant="outlined"
                    onClick={() => onNavigateRoute('/trace', gapId)}
                    aria-label={`P0 metric ${m.metric}: ${formatMetricVal(
                      m.value
                    )}. Activate to open trace replay.`}
                    sx={{
                      minHeight: 72,
                      minWidth: 0,
                      p: 1.25,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      textAlign: 'left',
                      whiteSpace: 'normal',
                      backgroundColor: tokens.surfaceSubtle,
                    }}
                  >
                    <Typography
                      className="mono-tabular"
                      sx={{
                        fontSize: '0.88rem',
                        fontWeight: 700,
                        color: tokens.amberAlertText,
                      }}
                    >
                      {formatMetricVal(m.value)}
                    </Typography>
                    <Typography
                      className="mono-tabular"
                      sx={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: tokens.textPrimary,
                        mt: 0.25,
                        overflowWrap: 'anywhere',
                        wordBreak: 'break-word',
                      }}
                    >
                      {m.metric}
                    </Typography>
                    <Typography variant="caption" sx={{ color: tokens.textSecondary, mt: 0.25 }}>
                      {P0_DEFINITIONS[m.metric] ?? ''}
                    </Typography>
                  </Button>
                ))}
              </Box>
            </Paper>

            {/* Below the fold: P1 Metrics Table sorted by change since last build */}
            <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
              <Typography variant="h2" component="h2" sx={{ mb: 0.5 }}>
                P1 Regression Metrics (Sorted by Change Since Last Build)
              </Typography>
              <Typography variant="body2" sx={{ color: tokens.textSecondary, mb: 1.5 }}>
                Pass rule: No regression beyond tolerance (2× standard deviation across 3 runs, min 1 pp).
              </Typography>

              <Box sx={{ overflowX: 'auto' }}>
                <Box
                  component="table"
                  aria-label="P1 regression metrics table"
                  sx={{ width: '100%', borderCollapse: 'collapse' }}
                >
                  <thead>
                    <tr>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.76rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Metric
                      </Box>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.76rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Value
                      </Box>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.76rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Change vs Last Build
                      </Box>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.76rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Trace
                      </Box>
                    </tr>
                  </thead>
                  <tbody>
                    {evalsModel.p1Metrics.map((m) => (
                      <tr key={m.metric}>
                        <Box component="td" sx={{ p: 1, borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                          <Typography className="mono-tabular" sx={{ fontSize: '0.8rem', fontWeight: 700 }}>
                            {m.metric}
                          </Typography>
                          <Typography variant="caption" sx={{ color: tokens.textSecondary }}>
                            {P1_DEFINITIONS[m.metric] ?? ''}
                          </Typography>
                        </Box>
                        <Box component="td" className="mono-tabular" sx={{ p: 1, fontSize: '0.8rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                          {formatMetricVal(m.value)}
                        </Box>
                        <Box component="td" className="mono-tabular" sx={{ p: 1, fontSize: '0.8rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                          {formatMetricVal(m.change_since_last ?? null)}
                        </Box>
                        <Box component="td" sx={{ p: 1, borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                          <Button
                            variant="outlined"
                            size="small"
                            onClick={() => onNavigateRoute('/trace', gapId)}
                            sx={{ minHeight: 48, fontSize: '0.75rem' }}
                          >
                            Open Trace
                          </Button>
                        </Box>
                      </tr>
                    ))}
                  </tbody>
                </Box>
              </Box>
            </Paper>

            {/* Per-Slice Tables: Parse Accuracy & Guard (Gemma vs Gemini Baseline) */}
            <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
              <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
                Per-Language-Slice Tables (Parsing &amp; Guard Comparison)
              </Typography>

              <Box sx={{ overflowX: 'auto' }}>
                <Box
                  component="table"
                  aria-label="Per-slice parsing accuracy and guard comparison table"
                  sx={{ width: '100%', borderCollapse: 'collapse' }}
                >
                  <thead>
                    <tr>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.75rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Language Slice
                      </Box>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.75rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        parse_accuracy
                      </Box>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.75rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Gemma Guard Recall
                      </Box>
                      <Box component="th" scope="col" sx={{ textAlign: 'left', p: 1, fontSize: '0.75rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                        Gemini Baseline Recall
                      </Box>
                    </tr>
                  </thead>
                  <tbody>
                    {evalsModel.sliceTables.guardComparisonBySlice.map((row, idx) => {
                      const parseRow = evalsModel.sliceTables.parseAccuracyBySlice[idx];
                      return (
                        <tr key={row.slice}>
                          <Box component="td" sx={{ p: 1, fontSize: '0.8rem', fontWeight: 600, borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                            {row.slice}
                          </Box>
                          <Box component="td" className="mono-tabular" sx={{ p: 1, fontSize: '0.78rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                            {formatMetricVal(parseRow?.value ?? null)}
                          </Box>
                          <Box component="td" className="mono-tabular" sx={{ p: 1, fontSize: '0.78rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                            {formatMetricVal(row.gemmaRecall)}
                          </Box>
                          <Box component="td" className="mono-tabular" sx={{ p: 1, fontSize: '0.78rem', borderBottom: `1px solid ${tokens.borderSubtle}` }}>
                            {formatMetricVal(row.geminiBaselineRecall)}
                          </Box>
                        </tr>
                      );
                    })}
                  </tbody>
                </Box>
              </Box>
            </Paper>

            {/* Collapsed P2 Metrics (§11.5) */}
            <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
              <Button
                fullWidth
                variant="outlined"
                onClick={() => setP2Expanded((prev) => !prev)}
                aria-expanded={p2Expanded}
                aria-controls="p2-metrics-panel"
                sx={{
                  minHeight: 48,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontWeight: 700,
                }}
              >
                <span>P2 Advisory Metrics (message_quality, latency_p95 · Warn Only)</span>
                {p2Expanded ? (
                  <ExpandLessIcon aria-hidden="true" />
                ) : (
                  <ExpandMoreIcon aria-hidden="true" />
                )}
              </Button>

              {p2Expanded && (
                <Box id="p2-metrics-panel" sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {evalsModel.p2Metrics.map((m) => (
                    <Box
                      key={m.metric}
                      sx={{
                        p: 1.25,
                        borderRadius: 1.5,
                        backgroundColor: tokens.surfaceSubtle,
                        display: 'flex',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: 1,
                      }}
                    >
                      <Box>
                        <Typography className="mono-tabular" sx={{ fontSize: '0.82rem', fontWeight: 700 }}>
                          {m.metric}
                        </Typography>
                        <Typography variant="caption" sx={{ color: tokens.textSecondary }}>
                          {P2_DEFINITIONS[m.metric] ?? ''}
                        </Typography>
                      </Box>
                      <Typography className="mono-tabular" sx={{ fontSize: '0.82rem', fontWeight: 700 }}>
                        {formatMetricVal(m.value)}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Paper>
          </Box>

          {/* Side Panel: Pinned Model IDs, Prompt Hashes & Build History (§11.5) */}
          <Box
            component="aside"
            aria-label="Pinned Models and Build History Side Panel"
            sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}
          >
            <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
              <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
                Pinned Model IDs &amp; Prompt Hashes
              </Typography>
              {evalsModel.latestRun ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Object.entries(evalsModel.latestRun.models).map(([role, meta]) => (
                    <Box key={role} sx={{ p: 1, borderRadius: 1.5, backgroundColor: tokens.surfaceSubtle }}>
                      <Typography sx={{ fontSize: '0.8rem', fontWeight: 700 }}>{role}</Typography>
                      <Typography className="mono-tabular" sx={{ fontSize: '0.75rem' }}>
                        {meta.model_id} · {meta.prompt_hash ?? 'no-hash'}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              ) : (
                <Typography className="mono-tabular" sx={{ fontSize: '0.84rem', color: tokens.amberAlertText }}>
                  No eval run yet (pinned model IDs and prompt hashes load from BigQuery covercall_evals.runs)
                </Typography>
              )}
            </Paper>

            <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
              <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
                Build History (including Blocked Gate Slot)
              </Typography>
              {evalsModel.buildHistory.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {evalsModel.buildHistory.map((b) => (
                    <Box key={b.run_id} sx={{ p: 1, borderRadius: 1.5, backgroundColor: tokens.surfaceSubtle }}>
                      <Typography className="mono-tabular" sx={{ fontSize: '0.8rem', fontWeight: 700 }}>
                        {b.build_id} · {b.status}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              ) : (
                <Typography className="mono-tabular" sx={{ fontSize: '0.84rem', color: tokens.amberAlertText }}>
                  No eval run yet (Cloud Build history and demonstration blocked build appear here once CI runs)
                </Typography>
              )}
            </Paper>
          </Box>
        </Box>
      )}

      {/* ROUTE 2: /trace/:gapId (§12.3 & §Step 4) */}
      {activeRoute === '/trace' && (
        <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 1,
              mb: 1.5,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AccountTreeOutlinedIcon sx={{ color: tokens.brandPrimary }} aria-hidden="true" />
              <Typography variant="h1" component="h1">
                Trace Replay (/trace/{gapId})
              </Typography>
            </Box>

            <Box
              data-testid="chain-verification-status"
              sx={{
                px: 1.25,
                py: 0.5,
                borderRadius: 1.5,
                backgroundColor:
                  chainVerified === true ? tokens.legalPassBg : tokens.amberAlertBg,
                color: chainVerified === true ? tokens.legalPassText : tokens.amberAlertText,
                border: `1px solid ${
                  chainVerified === true ? tokens.legalPassBorder : tokens.amberAlertBorder
                }`,
              }}
            >
              <Typography className="mono-tabular" sx={{ fontSize: '0.78rem', fontWeight: 700 }}>
                {chainVerified === true
                  ? 'Hash Chain: Verified'
                  : 'Hash Chain: Not verified (mock mode)'}
              </Typography>
            </Box>
          </Box>

          {/* Link-out slots for Cloud Workflows execution and Cloud Trace (§Step 4) */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 1.5,
              p: 1.5,
              mb: 2,
              borderRadius: 2,
              backgroundColor: tokens.surfaceSubtle,
              border: `1px solid ${tokens.borderSubtle}`,
            }}
          >
            <Box>
              <Typography variant="caption" sx={{ color: tokens.textSecondary, display: 'block' }}>
                Cloud Workflows Execution Slot
              </Typography>
              <Typography className="mono-tabular" sx={{ fontSize: '0.84rem', fontWeight: 700 }}>
                {workflowExecutionId}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <MockDataBadge isMockMode={isMockMode} label="External links inactive in mock mode" />
              <Button
                variant="outlined"
                size="small"
                disabled={isMockMode}
                aria-label="Open Cloud Workflows execution history"
                sx={{ minHeight: 48, fontSize: '0.78rem' }}
              >
                <span>Cloud Workflows Execution</span>
                <OpenInNewIcon sx={{ fontSize: 14, ml: 0.5 }} aria-hidden="true" />
              </Button>
              <Button
                variant="outlined"
                size="small"
                disabled={isMockMode}
                aria-label="Open Cloud Trace waterfall"
                sx={{ minHeight: 48, fontSize: '0.78rem' }}
              >
                <span>Cloud Trace</span>
                <OpenInNewIcon sx={{ fontSize: 14, ml: 0.5 }} aria-hidden="true" />
              </Button>
            </Box>
          </Box>

          {/* Event Timeline from gaps/{gapId}/events */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {traceEvents.map((ev) => (
              <Box
                key={ev.seq}
                sx={{
                  p: 1.5,
                  borderRadius: 2,
                  backgroundColor: tokens.surfaceSubtle,
                  border: `1px solid ${tokens.borderSubtle}`,
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 1,
                    mb: 0.5,
                  }}
                >
                  <Typography className="mono-tabular" sx={{ fontSize: '0.84rem', fontWeight: 700 }}>
                    seq #{ev.seq} · {ev.type} ({ev.from_state} → {ev.to_state})
                  </Typography>
                  <Typography
                    variant="caption"
                    className="mono-tabular"
                    sx={{ color: tokens.textMuted }}
                  >
                    {formatTime12h(ev.ts)} · trace_id: {ev.trace_id}
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ mb: 0.5 }}>
                  {String(ev.payload.summary ?? JSON.stringify(ev.payload))}
                </Typography>
                <Typography
                  variant="caption"
                  className="mono-tabular"
                  sx={{ color: tokens.textSecondary, display: 'block' }}
                >
                  actor: {ev.actor} · model_ids:{' '}
                  {ev.model_ids.length > 0 ? `[${ev.model_ids.join(', ')}]` : '[]'} · rule_ids: [
                  {ev.rule_ids.join(', ')}]
                </Typography>
                <Typography
                  variant="caption"
                  className="mono-tabular"
                  sx={{ color: tokens.textMuted, display: 'block', mt: 0.25 }}
                >
                  hash: {ev.hash} · prev_hash: {ev.prev_hash.slice(0, 16)}…
                </Typography>
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {/* ROUTE 3: /about (§11.2 & §Step 4) */}
      {activeRoute === '/about' && (
        <Paper sx={{ p: 2, backgroundColor: tokens.surface }}>
          <Typography variant="h1" component="h1" sx={{ mb: 1 }}>
            About CoverCall
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            A shift lead at a small three-outlet café chain in Singapore (Bugis, Tampines, Jurong
            East) gets a sick call at 6:02am. They tell CoverCall by voice. CoverCall finds legal,
            low-cost replacements, including staff from another outlet. After the lead approves by
            voice or tap, it messages candidates one at a time, reads their replies, re-plans when
            someone declines or counter-offers, and escalates when time runs out. Every assignment
            is checked against the Singapore Employment Act by a constraint solver and an
            independent validator, never by a language model.
          </Typography>

          <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
            How to Try the Three Scenarios
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}>
            {SCENARIO_DESCRIPTORS.map((scen) => (
              <Box
                key={scen.key}
                sx={{
                  p: 1.25,
                  borderRadius: 1.5,
                  backgroundColor: tokens.surfaceSubtle,
                  border: `1px solid ${tokens.borderSubtle}`,
                }}
              >
                <Typography sx={{ fontSize: '0.88rem', fontWeight: 700 }}>
                  {scen.buttonLabel} (
                  {scen.scenarioCode !== scen.buttonLabel
                    ? `${scen.scenarioCode} · ${scen.journeyRef}`
                    : scen.journeyRef}
                  )
                </Typography>
                <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
                  {scen.oneLineSummary}
                </Typography>
              </Box>
            ))}
          </Box>

          <Typography variant="h2" component="h2" sx={{ mb: 1 }}>
            Pinned Model IDs (from Data Layer)
          </Typography>
          {evalsModel?.latestRun ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}>
              {Object.entries(evalsModel.latestRun.models).map(([role, meta]) => (
                <Typography key={role} className="mono-tabular" sx={{ fontSize: '0.82rem' }}>
                  {role}: {meta.model_id}
                </Typography>
              ))}
            </Box>
          ) : (
            <Typography
              className="mono-tabular"
              sx={{ fontSize: '0.84rem', color: tokens.amberAlertText, mb: 2 }}
            >
              No eval run yet — pinned model IDs load from config/models.yaml via the backend API.
            </Typography>
          )}

          <Box
            sx={{
              p: 1.5,
              borderRadius: 1.5,
              backgroundColor: tokens.surfaceSubtle,
              border: `1px solid ${tokens.borderSubtle}`,
            }}
          >
            <Typography sx={{ fontSize: '0.88rem', fontWeight: 700 }}>
              All data is synthetic (`synthetic: true`)
            </Typography>
            <Typography variant="body2" sx={{ color: tokens.textSecondary }}>
              All outlets, staff profiles, wages, rosters, and replies are synthetic. Statutory
              rules cite{' '}
              <Link href={MOM_HOURS_OVERTIME_REST_URL} target="_blank" rel="noopener noreferrer">
                MOM: Hours of work, overtime and rest day
              </Link>
              .
            </Typography>
          </Box>
        </Paper>
      )}
    </Box>
  );
};
