import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Box, Button, CssBaseline, Paper, ThemeProvider, Typography } from '@mui/material';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { createCoverCallTheme, DARK_TOKENS, LIGHT_TOKENS } from './theme';
import { VoiceStateBar } from './components/VoiceStateBar';
import { CaptionsPanel } from './components/CaptionsPanel';
import { ScenarioLauncher } from './components/ScenarioLauncher';
import { GapCard } from './components/GapCard';
import { CandidateList } from './components/CandidateList';
import { RosterMiniGrid } from './components/RosterMiniGrid';
import { CascadeTimeline } from './components/CascadeTimeline';
import { ApprovalCard } from './components/ApprovalCard';
import { EvidenceViews, type Route } from './components/EvidenceModalViews';
import { ReplayBanner } from './components/ReplayBanner';
import { ApiClient, apiBaseUrlFromEnv } from './data/apiClient';
import type { ScenarioDto } from './data/backendTypes';
import { createSource } from './data/source';
import type { LeadView } from './data/viewModel';
import type { CaptionExchange, VoiceMode, VoiceState } from './voice/types';
import { isClearAffirmativeTranscript, LiveVoiceProvider, PushToTalkProvider, TextProvider } from './voice/voiceProvider';

function routeFromLocation(): { route: Route; gap: string | null } {
  if (typeof window === 'undefined') return { route: '/', gap: null };
  const path = window.location.pathname;
  const trace = path.match(/^\/trace\/(.+)$/);
  if (trace) return { route: '/trace', gap: decodeURIComponent(trace[1]) };
  if (path.startsWith('/evals')) return { route: '/evals', gap: null };
  if (path.startsWith('/about')) return { route: '/about', gap: null };
  return { route: '/', gap: null };
}

export const App: React.FC = () => {
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('light');
  const theme = useMemo(() => createCoverCallTheme(themeMode), [themeMode]);
  const tokens = themeMode === 'light' ? LIGHT_TOKENS : DARK_TOKENS;

  const baseUrl = useMemo(() => apiBaseUrlFromEnv(), []);
  const source = useMemo(() => createSource(baseUrl), [baseUrl]);
  const apiClient = useMemo(() => (baseUrl ? new ApiClient(baseUrl) : null), [baseUrl]);
  const isReplay = source.kind === 'replay';

  const initial = useMemo(routeFromLocation, []);
  const [route, setRoute] = useState<Route>(initial.route);
  const [gapHandle, setGapHandle] = useState<string | null>(initial.gap);
  const [scenarios, setScenarios] = useState<ScenarioDto[]>([]);
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const [view, setView] = useState<LeadView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [captions, setCaptions] = useState<CaptionExchange[]>([]);
  const [voiceState, setVoiceState] = useState<VoiceState>(isReplay ? 'Offline' : 'Muted');
  const [voiceMode, setVoiceMode] = useState<VoiceMode>('text');
  const [voiceReason, setVoiceReason] = useState<string>(isReplay ? 'Recorded replay: text input is display-only.' : 'Text mode active.');
  const [announcement, setAnnouncement] = useState('');
  const spoken = useRef(new Set<string>());

  const say = useCallback((speaker: CaptionExchange['speaker'], text: string, at: string) => {
    setCaptions((prev) => [...prev.slice(-3), { id: `${speaker}-${Date.now()}-${prev.length}`, speaker, timestampIso: at, text, highlight: speaker === 'CoverCall' }]);
  }, []);

  useEffect(() => {
    source.listScenarios().then(setScenarios, (e: Error) => setError(e.message));
  }, [source]);

  useEffect(() => {
    if (!gapHandle) return undefined;
    return source.watch(
      gapHandle,
      (v) => {
        setView(v);
        setError(null);
      },
      (e) => setError(e.message)
    );
  }, [gapHandle, source]);

  // Server-written sentences (read-back, summary) become CoverCall captions, once each.
  useEffect(() => {
    if (!view) return;
    const lines: string[] = [];
    if (view.approval) lines.push(view.approval.readback);
    if (view.gap.state === 'ESCALATED') lines.push('Nobody accepted in time. Choose a fallback.');
    if (view.gap.summary) lines.push(view.gap.summary);
    if (view.gap.state === 'RESOLVED' && view.gap.outcomeLabel) lines.push(`Resolved: ${view.gap.outcomeLabel}.`);
    for (const line of lines) {
      if (!spoken.current.has(line)) {
        spoken.current.add(line);
        say('CoverCall', line, view.now);
      }
    }
    setAnnouncement(`Gap ${view.gap.gapId} is ${view.gap.state}.`);
  }, [view, say]);

  const navigate = (next: Route) => {
    setRoute(next);
    if (typeof window !== 'undefined' && window.history?.pushState) {
      window.history.pushState({}, '', next === '/trace' && gapHandle ? `/trace/${encodeURIComponent(gapHandle)}` : next);
    }
  };

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const startScenario = (scenarioId: string) =>
    run(async () => {
      const handle = await source.start(scenarioId);
      spoken.current = new Set();
      setCaptions([]);
      setView(null);
      setActiveScenarioId(scenarioId);
      setGapHandle(handle);
      setRoute('/');
    });

  const decide = (decision: 'approve' | 'reject') =>
    run(async () => {
      if (!gapHandle || !view?.approval) throw new Error('No approval is pending.');
      await source.approve(gapHandle, view.approval.nonce, decision);
    });

  const chooseFallback = (option: string) =>
    run(async () => {
      if (!gapHandle) throw new Error('No active gap.');
      await source.chooseFallback(gapHandle, option);
    });

  const cancel = () =>
    run(async () => {
      if (!gapHandle) throw new Error('No active gap.');
      await source.cancel(gapHandle);
      say('CoverCall', 'Cancel requested. The workflow will withdraw open offers.', view?.now ?? new Date().toISOString());
    });

  const submitText = (text: string) => {
    const at = view?.now ?? new Date().toISOString();
    say('Lead', text, at);
    if (isReplay) {
      say('CoverCall', 'Recorded replay: typed input is not sent anywhere.', at);
      return;
    }
    if (view?.approval && gapHandle) {
      // The server decides: only a clear affirmative in the transcript counts as approval (§5.3).
      void run(() => source.approve(gapHandle, view.approval!.nonce, isClearAffirmativeTranscript(text) ? 'approve' : 'reject', text));
      return;
    }
    say('CoverCall', 'Typed absence reports are not parsed in the browser. Use voice (hands-free or push-to-talk) or a scenario button.', at);
  };

  const voiceRef = useRef<{ disconnect(): void; setTalking?(open: boolean): void } | null>(null);
  const [talking, setTalking] = useState(false);
  const talk = (open: boolean) => {
    if (talking === open) return;
    setTalking(open);
    voiceRef.current?.setTalking?.(open);
  };

  const requestVoiceMode = async (mode: VoiceMode) => {
    voiceRef.current?.disconnect();
    voiceRef.current = null;
    // The voice tools act on the gap they create; the lead view follows it (nothing runs locally).
    const context = {
      gapId: gapHandle,
      onGap: (id: string) => {
        setView(null);
        setActiveScenarioId(null);
        setGapHandle(id);
        setRoute('/');
      },
    };
    const callbacks = {
      onStateChange: (st: VoiceState, reason?: string) => {
        setVoiceState(st);
        if (reason) setVoiceReason(reason);
      },
      onModeFallback: (fallback: VoiceMode, reason: string) => {
        setVoiceMode(fallback);
        setVoiceReason(reason);
        setAnnouncement(reason);
      },
      onCaption: (speaker: 'Lead' | 'CoverCall', text: string) => say(speaker, text, view?.now ?? new Date().toISOString()),
    };
    setVoiceMode(mode);
    const provider =
      mode === 'hands-free'
        ? new LiveVoiceProvider(apiClient, callbacks, null, context)
        : mode === 'push-to-talk'
          ? new PushToTalkProvider(apiClient, callbacks, null, context)
          : new TextProvider(apiClient, callbacks);
    voiceRef.current = provider;
    await provider.connect();
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: tokens.canvas, color: tokens.textPrimary }}>
        <VoiceStateBar
          voiceState={voiceState}
          voiceMode={voiceMode}
          voiceReason={voiceReason}
          isReplay={isReplay}
          themeMode={themeMode}
          onChangeVoiceState={setVoiceState}
          onChangeVoiceMode={(m) => void requestVoiceMode(m)}
          onToggleTheme={() => setThemeMode((p) => (p === 'light' ? 'dark' : 'light'))}
          onSubmitUtterance={submitText}
        />
        <ReplayBanner show={isReplay} />

        <Box component="main" id="main-content" sx={{ flex: 1, width: '100%', maxWidth: 1080, mx: 'auto', px: { xs: 1.5, sm: 2.5 }, pt: 1.5, pb: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {error && (
            <Paper role="alert" data-testid="error-banner" sx={{ p: 1.5, backgroundColor: tokens.ruleWarnBg, color: tokens.ruleWarnText, border: `1.5px solid ${tokens.ruleWarnBorder}` }}>
              <Typography sx={{ fontWeight: 700 }}>Something went wrong</Typography>
              <Typography variant="body2">{error}</Typography>
            </Paper>
          )}

          {route !== '/' ? (
            <EvidenceViews activeRoute={route} gapHandle={gapHandle} source={source} scenarios={scenarios} onNavigate={navigate} />
          ) : (
            <>
              <ScenarioLauncher scenarios={scenarios} activeScenarioId={activeScenarioId} busy={busy} onStart={(id) => void startScenario(id)} />
              {gapHandle && !view && !error && <Typography role="status">Loading the gap…</Typography>}
              {!isReplay && voiceMode !== 'text' && (
                <Typography variant="body2" data-testid="voice-hint" sx={{ color: 'text.secondary' }}>
                  Try: &ldquo;Ali is sick for the 7am barista shift at Bugis on Tuesday, 3 November.&rdquo;
                </Typography>
              )}
              {voiceMode === 'push-to-talk' && !isReplay && (
                <Button
                  variant={talking ? 'contained' : 'outlined'}
                  aria-pressed={talking}
                  onPointerDown={() => talk(true)}
                  onPointerUp={() => talk(false)}
                  onPointerLeave={() => talk(false)}
                  onKeyDown={(e) => {
                    if (e.key === ' ' || e.key === 'Enter') {
                      e.preventDefault();
                      talk(true);
                    }
                  }}
                  onKeyUp={() => talk(false)}
                  sx={{ alignSelf: 'flex-start', minHeight: 48 }}
                >
                  {talking ? 'Listening… release to stop' : 'Hold to talk'}
                </Button>
              )}
              {!view && (captions.length > 0 || voiceMode !== 'text') && (
                <CaptionsPanel captions={captions} voiceState={voiceState} statusAnnouncement={announcement} isReplay={isReplay} />
              )}
              {view && (
                <>
                  <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1.15fr 0.85fr' }, gap: 2, alignItems: 'start' }}>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <CaptionsPanel captions={captions} voiceState={voiceState} statusAnnouncement={announcement} isReplay={isReplay} />
                      <GapCard gap={view.gap} naiveName={view.naive?.name ?? null} isReplay={isReplay} canAct={source.canAct} onInspectTrace={() => navigate('/trace')} onCancel={() => void cancel()} />
                      <CandidateList view={view} />
                    </Box>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                      <RosterMiniGrid view={view} />
                      <CascadeTimeline view={view} />
                    </Box>
                  </Box>
                  <ApprovalCard view={view} canAct={source.canAct} busy={busy} onDecide={(d) => void decide(d)} onChooseFallback={(o) => void chooseFallback(o)} />
                </>
              )}
            </>
          )}
        </Box>

        <Box component="footer" sx={{ mt: 'auto', borderTop: `1px solid ${tokens.borderSubtle}`, backgroundColor: tokens.surface, px: 2, py: 2 }}>
          <Box sx={{ maxWidth: 1080, mx: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>
              All data is synthetic
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button variant="outlined" size="small" onClick={() => navigate('/evals')} sx={{ minHeight: 48 }}>
                <VerifiedUserOutlinedIcon sx={{ fontSize: 16, mr: 0.75 }} aria-hidden="true" />
                How we know it&apos;s safe
              </Button>
              <Button variant="outlined" size="small" disabled={!gapHandle} onClick={() => navigate('/trace')} sx={{ minHeight: 48 }}>
                <AccountTreeOutlinedIcon sx={{ fontSize: 16, mr: 0.75 }} aria-hidden="true" />
                Trace replay
              </Button>
              <Button variant="outlined" size="small" onClick={() => navigate('/about')} sx={{ minHeight: 48 }}>
                <InfoOutlinedIcon sx={{ fontSize: 16, mr: 0.75 }} aria-hidden="true" />
                About
              </Button>
            </Box>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;
