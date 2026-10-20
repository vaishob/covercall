import { OUTPUT_RATE } from './pcm.ts';

/**
 * The input (mic capture) and output (model speech) AudioContexts, shared by every Live session.
 * iOS starts a context suspended unless it is created or resumed inside a user tap, so
 * `primeAudio()` must be called synchronously in the tap handler, before any `await`.
 */
export interface AudioPair {
  input: AudioContext;
  output: AudioContext;
}

let pair: AudioPair | null = null;

function newOutputContext(): AudioContext {
  try {
    return new AudioContext({ sampleRate: OUTPUT_RATE });
  } catch {
    return new AudioContext(); // buffers are created at OUTPUT_RATE; the context resamples
  }
}

/** Creates (or reuses) both contexts and calls resume() on them. Null where Web Audio is missing. */
export function primeAudio(): AudioPair | null {
  if (typeof AudioContext === 'undefined') return null;
  if (!pair || pair.input.state === 'closed' || pair.output.state === 'closed') {
    pair = { input: new AudioContext(), output: newOutputContext() };
  }
  for (const ctx of [pair.input, pair.output]) void ctx.resume().catch(() => undefined);
  return pair;
}

const worklets = new WeakMap<AudioContext, Promise<void>>();

/** Loads the capture worklet once per context (a second registerProcessor would throw). */
export function ensureCaptureWorklet(ctx: AudioContext): Promise<void> {
  let loading = worklets.get(ctx);
  if (!loading) {
    loading = ctx.audioWorklet.addModule('/pcm-capture.worklet.js');
    loading.catch(() => worklets.delete(ctx));
    worklets.set(ctx, loading);
  }
  return loading;
}

export function audioRunning(audio: AudioPair): boolean {
  return audio.input.state === 'running' && audio.output.state === 'running';
}

/** Outside a tap this works only if the contexts were unlocked before (e.g. after getUserMedia). */
export async function tryResume(audio: AudioPair, timeoutMs = 500): Promise<boolean> {
  const resumed = Promise.all([audio.input.resume(), audio.output.resume()]).catch(() => undefined);
  await Promise.race([resumed, new Promise((r) => setTimeout(r, timeoutMs))]);
  return audioRunning(audio);
}
