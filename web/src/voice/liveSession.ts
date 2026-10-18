/**
 * Browser Live API session (Gemini Live, v1beta, ephemeral token only; decision 0019).
 * The token locks model, tools and system instruction server-side; this file adds nothing to them.
 * Mic -> AudioWorklet -> 16 kHz PCM16 40 ms chunks -> sendRealtimeInput. Model audio (24 kHz PCM16)
 * is queued gaplessly and stopped at once on `interrupted`. Tool calls go to `onToolCall` (api).
 */
import { GoogleGenAI, type LiveServerMessage, type Session } from '@google/genai';
import { base64ToPcm16, Chunker, OUTPUT_RATE, pcm16ToBase64, pcm16ToFloat } from './pcm.ts';

export interface LiveSessionHandlers {
  onUserTranscript: (text: string) => void;
  onModelTranscript: (text: string) => void;
  onSpeaking: (speaking: boolean) => void;
  onToolCall: (name: string, args: Record<string, string>) => Promise<unknown>;
  onClosed: (reason: string) => void;
}

export class LiveSession {
  private session: Session | null = null;
  private mic: MediaStream | null = null;
  private ctxIn: AudioContext | null = null;
  private ctxOut: AudioContext | null = null;
  private playAt = 0;
  private sources: AudioBufferSourceNode[] = [];
  private gate = true;
  private userText = '';
  private modelText = '';
  private closed = false;
  private readonly handlers: LiveSessionHandlers;

  constructor(handlers: LiveSessionHandlers) {
    this.handlers = handlers;
  }

  /** The lead's latest complete utterance (sent with `approve` so the server checks the words). */
  lastUserTranscript = '';

  async open(token: string, model: string, apiVersion: string): Promise<void> {
    // Mic first: a denial falls back before a token use is spent on a socket.
    this.mic = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    const ai = new GoogleGenAI({ apiKey: token, httpOptions: { apiVersion } });
    this.session = await ai.live.connect({
      model,
      config: {}, // everything is locked by the token
      callbacks: {
        onmessage: (m: LiveServerMessage) => void this.onMessage(m),
        onerror: () => this.close('Live socket error.'),
        onclose: (e: CloseEvent) => this.close(e.reason ? `Live session closed: ${e.reason}` : 'Live session closed.'),
      },
    });
    this.ctxOut = new AudioContext({ sampleRate: OUTPUT_RATE });
    this.ctxIn = new AudioContext();
    await this.ctxIn.audioWorklet.addModule('/pcm-capture.worklet.js');
    const node = new AudioWorkletNode(this.ctxIn, 'pcm-capture');
    const chunker = new Chunker(this.ctxIn.sampleRate);
    node.port.onmessage = (e: MessageEvent<Float32Array>) => {
      if (!this.gate || !this.session) return;
      for (const pcm of chunker.push(e.data)) {
        this.session.sendRealtimeInput({ audio: { data: pcm16ToBase64(pcm), mimeType: 'audio/pcm;rate=16000' } });
      }
    };
    this.ctxIn.createMediaStreamSource(this.mic).connect(node);
  }

  /** Push-to-talk: the same session, with the mic gated by a held button. */
  setGate(open: boolean): void {
    this.gate = open;
    if (!open) this.session?.sendRealtimeInput({ audioStreamEnd: true });
  }

  private async onMessage(m: LiveServerMessage): Promise<void> {
    const sc = m.serverContent;
    if (sc?.interrupted) this.stopPlayback();
    if (sc?.inputTranscription?.text) this.userText += sc.inputTranscription.text;
    if (sc?.outputTranscription?.text) this.modelText += sc.outputTranscription.text;
    for (const part of sc?.modelTurn?.parts ?? []) {
      if (part.inlineData?.data && part.inlineData.mimeType?.startsWith('audio/pcm')) this.play(part.inlineData.data);
    }
    if (sc?.turnComplete || sc?.interrupted || m.toolCall) this.flushCaptions();
    for (const call of m.toolCall?.functionCalls ?? []) {
      let response: Record<string, unknown>;
      try {
        response = { result: await this.handlers.onToolCall(call.name ?? '', (call.args ?? {}) as Record<string, string>) };
      } catch (err) {
        response = { error: err instanceof Error ? err.message : 'tool call failed' };
      }
      this.session?.sendToolResponse({ functionResponses: [{ id: call.id, name: call.name, response }] });
    }
  }

  private flushCaptions(): void {
    if (this.userText.trim()) {
      this.lastUserTranscript = this.userText.trim();
      this.handlers.onUserTranscript(this.lastUserTranscript);
    }
    if (this.modelText.trim()) this.handlers.onModelTranscript(this.modelText.trim());
    this.userText = '';
    this.modelText = '';
  }

  private play(b64: string): void {
    const ctx = this.ctxOut;
    if (!ctx) return;
    const samples = pcm16ToFloat(base64ToPcm16(b64));
    const buf = ctx.createBuffer(1, samples.length, OUTPUT_RATE);
    buf.copyToChannel(samples, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    this.playAt = Math.max(this.playAt, ctx.currentTime); // gapless: schedule back to back
    src.start(this.playAt);
    this.playAt += buf.duration;
    this.sources.push(src);
    this.handlers.onSpeaking(true);
    src.onended = () => {
      this.sources = this.sources.filter((s) => s !== src);
      if (!this.sources.length) this.handlers.onSpeaking(false);
    };
  }

  private stopPlayback(): void {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    }
    this.sources = [];
    this.playAt = 0;
    this.handlers.onSpeaking(false);
  }

  close(reason = 'Voice session closed (no audio stored).'): void {
    if (this.closed) return;
    this.closed = true;
    this.stopPlayback();
    this.mic?.getTracks().forEach((t) => t.stop());
    void this.ctxIn?.close();
    void this.ctxOut?.close();
    try {
      this.session?.close();
    } catch {
      /* already closed */
    }
    this.session = null;
    this.handlers.onClosed(reason);
  }
}
