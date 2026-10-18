import React, { useMemo, useState } from 'react';
import {
  Box,
  Button,
  CssBaseline,
  Link,
  ThemeProvider,
  Typography,
} from '@mui/material';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import {
  ApprovalRecord,
  CaptionExchange,
  EscalationFallbackOption,
  FeasibleCandidate,
  GapRecord,
  MOM_HOURS_OVERTIME_REST_URL,
  SCENARIO_MAP,
  ScenarioKey,
  VoiceMode,
  VoiceState,
} from './mocks/state';
import { createCoverCallTheme, DARK_TOKENS, LIGHT_TOKENS } from './theme';
import { VoiceStateBar } from './components/VoiceStateBar';
import { CaptionsPanel } from './components/CaptionsPanel';
import { ScenarioLauncher } from './components/ScenarioLauncher';
import { GapCard } from './components/GapCard';
import { CandidateList } from './components/CandidateList';
import { RosterMiniGrid } from './components/RosterMiniGrid';
import { CascadeTimeline } from './components/CascadeTimeline';
import { ApprovalCard } from './components/ApprovalCard';
import { EvidenceViews } from './components/EvidenceModalViews';
import { MockModeBanner } from './components/MockModeBanner';
import { createDataSourceFromEnv } from './data/dataSource';
import { createApiClientFromEnv } from './data/apiClient';
import {
  isClearAffirmativeTranscript,
  LiveVoiceProvider,
  PushToTalkProvider,
  TextProvider,
} from './voice/voiceProvider';
import { formatCurrencySGD, formatTime12h } from './utils/formatters';

function parseInitialRouteFromLocation(): '/' | '/evals' | '/trace' | '/about' {
  if (typeof window === 'undefined') return '/';
  const path = window.location.pathname;
  if (path.startsWith('/evals')) return '/evals';
  if (path.startsWith('/trace')) return '/trace';
  if (path.startsWith('/about')) return '/about';
  return '/';
}

export const App: React.FC = () => {
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('light');
  const theme = useMemo(() => createCoverCallTheme(themeMode), [themeMode]);
  const tokens = themeMode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const dataSource = useMemo(() => createDataSourceFromEnv(), []);
  const apiClient = useMemo(() => createApiClientFromEnv(), []);
  const isMockMode = dataSource.isMock || apiClient.isMockMode;

  const [activeRoute, setActiveRoute] = useState<'/' | '/evals' | '/trace' | '/about'>(
    parseInitialRouteFromLocation
  );
  const [scenarioKey, setScenarioKey] = useState<ScenarioKey>('s017');
  const activeBundle =
    scenarioKey === 'empty' ? SCENARIO_MAP.s017 : SCENARIO_MAP[scenarioKey];

  const navigateToRoute = (
    route: '/' | '/evals' | '/trace' | '/about',
    targetGapId?: string
  ) => {
    setActiveRoute(route);
    if (typeof window !== 'undefined' && window.history?.pushState) {
      const urlPath =
        route === '/trace' ? `/trace/${targetGapId ?? gap.id}` : route;
      window.history.pushState({}, '', urlPath);
    }
  };

  const [voiceState, setVoiceState] = useState<VoiceState>(
    activeBundle.defaultVoiceState
  );
  const [voiceMode, setVoiceMode] = useState<VoiceMode>(
    activeBundle.defaultVoiceMode
  );
  const [voiceReason, setVoiceReason] = useState<string>(
    isMockMode
      ? 'Voice unavailable in mock mode (no API URL). Text mode active.'
      : 'Voice ready'
  );
  const [captions, setCaptions] = useState<CaptionExchange[]>(activeBundle.captions);
  const [gap, setGap] = useState<GapRecord>(activeBundle.gap);
  const [candidates, setCandidates] = useState<FeasibleCandidate[]>(
    activeBundle.candidates
  );
  const [selectedRank, setSelectedRank] = useState<number>(1);
  const [approval, setApproval] = useState<ApprovalRecord>(activeBundle.approval);
  const [cascadeStepCount, setCascadeStepCount] = useState<number>(
    activeBundle.cascadeOffers.length
  );
  const [isReSolving, setIsReSolving] = useState<boolean>(false);
  const [selectedEscalationId, setSelectedEscalationId] =
    useState<EscalationFallbackOption['id']>('borrow_cross_outlet');
  const [statusAnnouncement, setStatusAnnouncement] = useState<string>(
    'Loaded Scenario S-017 mock state: Bugis opener sick call at 6:02am.'
  );

  const handleVoiceModeRequest = async (requestedMode: VoiceMode) => {
    const callbacks = {
      onStateChange: (st: VoiceState, reason?: string) => {
        setVoiceState(st);
        if (reason) setVoiceReason(reason);
      },
      onModeFallback: (fallbackMode: VoiceMode, reason: string) => {
        setVoiceMode(fallbackMode);
        setVoiceReason(reason);
        setStatusAnnouncement(reason);
      },
      onCaption: (speaker: 'Lead' | 'CoverCall', text: string) => {
        setCaptions((prev) => [
          ...prev.slice(-2),
          {
            id: `cap-${Date.now()}`,
            speaker,
            timestampIso: '2026-11-03T06:02:30+08:00',
            text,
          },
        ]);
      },
    };

    const envModelId =
      (typeof import.meta !== 'undefined' &&
        (import.meta as unknown as { env?: Record<string, string | undefined> }).env
          ?.VITE_GEMINI_LIVE_MODEL_ID) ||
      null;

    if (requestedMode === 'hands-free') {
      const provider = new LiveVoiceProvider(apiClient, callbacks, envModelId);
      setVoiceMode('hands-free');
      await provider.connect();
      return;
    }

    if (requestedMode === 'push-to-talk') {
      const provider = new PushToTalkProvider(apiClient, callbacks, envModelId);
      setVoiceMode('push-to-talk');
      await provider.connect();
      return;
    }

    const textProvider = new TextProvider(apiClient, callbacks);
    setVoiceMode('text');
    await textProvider.connect();
  };

  const handleSelectScenario = (nextKey: ScenarioKey) => {
    setScenarioKey(nextKey);
    setActiveRoute('/');
    if (nextKey === 'empty') {
      setVoiceState('Offline');
      setStatusAnnouncement(
        'Empty state loaded. Choose 6:02am sick call, Nobody replies, or Adversarial.'
      );
      return;
    }
    const nextBundle = SCENARIO_MAP[nextKey];
    setVoiceState(nextBundle.defaultVoiceState);
    setVoiceMode(nextBundle.defaultVoiceMode);
    setCaptions(nextBundle.captions);
    setGap(nextBundle.gap);
    setCandidates(nextBundle.candidates);
    setSelectedRank(1);
    setApproval(nextBundle.approval);
    setCascadeStepCount(nextBundle.cascadeOffers.length);
    setStatusAnnouncement(`Loaded Scenario ${nextBundle.scenarioCode}: ${nextBundle.title}`);
  };

  const handleSelectCandidate = (rank: number) => {
    setSelectedRank(rank);
    const chosen = candidates.find((c) => c.rank === rank);
    if (!chosen) return;
    setIsReSolving(true);
    window.setTimeout(() => setIsReSolving(false), 160);

    const newReadback = `Approve Plan #${chosen.rank} for Bugis Barista (7:00am–3:00pm): offer ${chosen.display_name} (${chosen.home_outlet}, arrives ${formatTime12h(
      chosen.arrival_iso
    )}, ${formatCurrencySGD(chosen.incremental_cost_sgd)}, saves ${formatCurrencySGD(
      chosen.saves_vs_overtime_sgd
    )} vs overtime), then cascade to remaining legal candidates.`;

    setApproval((prev) => ({
      ...prev,
      status: 'pending',
      readback_text: newReadback,
    }));
    setStatusAnnouncement(`Selected Plan #${chosen.rank} with ${chosen.display_name}.`);
  };

  const handleToggleChannel = (staffId: string) => {
    setCandidates((prev) =>
      prev.map((c) =>
        c.staff_id === staffId
          ? { ...c, channel: c.channel === 'telegram' ? 'sim' : 'telegram' }
          : c
      )
    );
    setStatusAnnouncement(`Switched connector channel for ${staffId}.`);
  };

  const handleApprovePlan = () => {
    if (scenarioKey === 'empty') {
      handleSelectScenario('s017');
      return;
    }
    const chosen = candidates.find((c) => c.rank === selectedRank) ?? candidates[0];
    setApproval((prev) => ({
      ...prev,
      status: 'approved',
      approved_via: voiceMode === 'hands-free' ? 'voice' : 'tap',
      approved_at_iso: '2026-11-03T06:02:14+08:00',
    }));
    setGap((prev) => ({
      ...prev,
      state: 'FILLED',
      version: prev.version + 1,
    }));

    const confirmExchange: CaptionExchange = {
      id: `cap-appr-${Date.now()}`,
      speaker: 'CoverCall',
      timestampIso: '2026-11-03T06:04:18+08:00',
      text: `Approved in mock mode (nonce ${approval.approval_nonce}): ${chosen.display_name} selected for Bugis 7:00am–3:00pm at ${formatCurrencySGD(
        chosen.incremental_cost_sgd
      )} (mock data — not computed).`,
      highlight: true,
    };
    setCaptions((prev) => [...prev.slice(-2), confirmExchange]);
    setStatusAnnouncement(
      `Plan approved in mock mode for ${chosen.display_name}.`
    );
  };

  const handleRejectOrEdit = () => {
    const nextRank = selectedRank === 1 ? 2 : 1;
    handleSelectCandidate(nextRank);
    setApproval((prev) => ({
      ...prev,
      status: 'rejected',
    }));

    const nextCand = candidates.find((c) => c.rank === nextRank) ?? candidates[0];
    setCaptions((prev) => [
      ...prev.slice(-2),
      {
        id: `cap-edit-${Date.now()}`,
        speaker: 'CoverCall',
        timestampIso: '2026-11-03T06:02:20+08:00',
        text: `Switched mock recommendation to Plan #${nextCand.rank} (${nextCand.display_name}, arrives ${formatTime12h(
          nextCand.arrival_iso
        )}, saves ${formatCurrencySGD(nextCand.saves_vs_overtime_sgd)} mock).`,
        highlight: true,
      },
    ]);
    setStatusAnnouncement(
      `Switched mock recommendation to ${nextCand.display_name}.`
    );
  };

  const handleTriggerReSolve = () => {
    setIsReSolving(true);
    window.setTimeout(() => {
      setIsReSolving(false);
      setStatusAnnouncement('Roster mini-grid preview updated.');
    }, 170);
  };

  const handleAdvanceCascadeStep = () => {
    const total = activeBundle.cascadeOffers.length;
    setCascadeStepCount((prev) => (prev < total ? prev + 1 : 1));
  };

  const handleSelectEscalationOption = (opt: EscalationFallbackOption) => {
    setSelectedEscalationId(opt.id);
    setApproval((prev) => ({
      ...prev,
      status: 'pending',
      readback_text: `Escalation at t_esc (6:07am): Confirm ${opt.title} (${formatCurrencySGD(
        opt.cost_delta_sgd
      )} mock). ${opt.legal_note}`,
    }));
    setStatusAnnouncement(`Selected escalation fallback: ${opt.title}`);
  };

  const handleSubmitUtterance = (text: string) => {
    if (scenarioKey === 'empty') {
      setScenarioKey('s017');
    }
    const lower = text.toLowerCase();
    const leadMsg: CaptionExchange = {
      id: `cap-usr-${Date.now()}`,
      speaker: 'Lead',
      timestampIso: '2026-11-03T06:02:30+08:00',
      text,
    };

    if (isClearAffirmativeTranscript(text)) {
      setCaptions((prev) => [...prev.slice(-2), leadMsg]);
      handleApprovePlan();
      return;
    }

    if (lower.includes('double') || lower.includes('priya') || lower.includes('14')) {
      handleSelectScenario('adversarial');
      return;
    }

    const replyMsg: CaptionExchange = {
      id: `cap-sys-${Date.now() + 1}`,
      speaker: 'CoverCall',
      timestampIso: '2026-11-03T06:02:32+08:00',
      text: 'Received text input in mock mode: Bugis Barista 7:00am–3:00pm gap. Only a clear affirmative ("Yes, approve") approves the read-back; anything else counts as a no.',
      highlight: true,
    };
    setCaptions((prev) => [...prev.slice(-1), leadMsg, replyMsg]);
    setStatusAnnouncement('Processed lead text input in mock mode.');
  };

  const selectedCandidate =
    candidates.find((c) => c.rank === selectedRank) ?? candidates[0];

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />

      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: tokens.canvas,
          color: tokens.textPrimary,
        }}
      >
        {/* 1. Voice State Bar (Always visible at the top, §11.3 item 1) */}
        <VoiceStateBar
          voiceState={voiceState}
          voiceMode={voiceMode}
          voiceReason={voiceReason}
          isMockMode={isMockMode}
          themeMode={themeMode}
          onChangeVoiceState={(next) => {
            setVoiceState(next);
            setStatusAnnouncement(`Voice state changed to ${next}.`);
          }}
          onChangeVoiceMode={(mode) => {
            void handleVoiceModeRequest(mode);
          }}
          onToggleTheme={() =>
            setThemeMode((prev) => (prev === 'light' ? 'dark' : 'light'))
          }
          onSubmitUtterance={handleSubmitUtterance}
        />

        {/* Persistent Mock Mode Banner (§Step 2) */}
        <MockModeBanner
          isMockMode={isMockMode}
          sourceName={dataSource.sourceName}
          apiBaseUrl={apiClient.baseUrl}
        />

        {/* Main Content Container */}
        <Box
          component="main"
          id="main-content"
          sx={{
            flex: 1,
            width: '100%',
            maxWidth: 1080,
            mx: 'auto',
            px: { xs: 1.5, sm: 2.5 },
            pt: 1.5,
            pb: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
          }}
        >
          {activeRoute !== '/' ? (
            <EvidenceViews
              activeRoute={activeRoute}
              gapId={gap.id}
              workflowExecutionId={gap.workflow_execution_id}
              dataSource={dataSource}
              isMockMode={isMockMode}
              onBackToLeadView={() => navigateToRoute('/')}
              onNavigateRoute={navigateToRoute}
            />
          ) : (
            <>
              <ScenarioLauncher
                activeScenario={scenarioKey}
                onSelectScenario={handleSelectScenario}
              />

              {scenarioKey !== 'empty' && (
                <>
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: { xs: '1fr', lg: '1.15fr 0.85fr' },
                      gap: 2,
                      alignItems: 'start',
                    }}
                  >
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <CaptionsPanel
                        captions={captions}
                        voiceState={voiceState}
                        statusAnnouncement={statusAnnouncement}
                        isMockMode={isMockMode}
                      />

                      <GapCard
                        gap={gap}
                        isMockMode={isMockMode}
                        onInspectTrace={() => navigateToRoute('/trace', gap.id)}
                      />

                      <CandidateList
                        candidates={candidates}
                        rejectedCandidates={activeBundle.rejectedCandidates}
                        selectedRank={selectedRank}
                        isMockMode={isMockMode}
                        onSelectCandidate={handleSelectCandidate}
                        onToggleChannel={handleToggleChannel}
                      />
                    </Box>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <RosterMiniGrid
                        rows={activeBundle.rosterGrid}
                        selectedAssigneeName={selectedCandidate.display_name}
                        isReSolving={isReSolving}
                        isMockMode={isMockMode}
                        onTriggerReSolve={handleTriggerReSolve}
                      />

                      <CascadeTimeline
                        offers={activeBundle.cascadeOffers}
                        guardImpl={activeBundle.guardImpl}
                        isMockMode={isMockMode}
                        quarantinedMessage={activeBundle.quarantinedMessage}
                        activeStepCount={cascadeStepCount}
                        onAdvanceCascadeStep={handleAdvanceCascadeStep}
                      />
                    </Box>
                  </Box>

                  <ApprovalCard
                    approval={approval}
                    escalationOptions={activeBundle.escalationOptions}
                    selectedEscalationId={selectedEscalationId}
                    onApprove={handleApprovePlan}
                    onRejectOrEdit={handleRejectOrEdit}
                    onSelectEscalationOption={handleSelectEscalationOption}
                  />
                </>
              )}
            </>
          )}
        </Box>

        {/* 8. Footer: "All data is synthetic" + "How we know it's safe" link to /evals (§0 & §11.3 item 8) */}
        <Box
          component="footer"
          role="contentinfo"
          sx={{
            mt: 'auto',
            borderTop: `1px solid ${tokens.borderSubtle}`,
            backgroundColor: tokens.surface,
            px: 2,
            py: 2,
          }}
        >
          <Box
            sx={{
              maxWidth: 1080,
              mx: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 1,
              }}
            >
              <Typography variant="body2" sx={{ fontWeight: 700, color: tokens.textPrimary }}>
                All data is synthetic (`synthetic: true`) · No real employee PII
              </Typography>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigateToRoute('/evals')}
                  sx={{ minHeight: 48, fontSize: '0.8rem', fontWeight: 700 }}
                >
                  <VerifiedUserOutlinedIcon sx={{ fontSize: 16, mr: 0.75 }} aria-hidden="true" />
                  How we know it&apos;s safe (/evals)
                </Button>

                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigateToRoute('/trace', gap.id)}
                  sx={{ minHeight: 48, fontSize: '0.8rem' }}
                >
                  <AccountTreeOutlinedIcon sx={{ fontSize: 16, mr: 0.75 }} aria-hidden="true" />
                  Trace Replay
                </Button>

                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigateToRoute('/about')}
                  sx={{ minHeight: 48, fontSize: '0.8rem' }}
                >
                  <InfoOutlinedIcon sx={{ fontSize: 16, mr: 0.75 }} aria-hidden="true" />
                  About
                </Button>
              </Box>
            </Box>

            <Typography variant="caption" sx={{ color: tokens.textMuted }}>
              Statutory rules cite{' '}
              <Link
                href={MOM_HOURS_OVERTIME_REST_URL}
                target="_blank"
                rel="noopener noreferrer"
              >
                Ministry of Manpower (MOM): Hours of work, overtime and rest day
              </Link>
              . Wages and company rules are synthetic.
            </Typography>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;
