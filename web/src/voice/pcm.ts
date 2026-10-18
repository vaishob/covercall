/**
 * Pure PCM helpers for the Live API (no browser APIs, unit-tested).
 * Mic: Float32 at the device rate -> 16 kHz mono PCM16, ~40 ms chunks (640 samples).
 * Playback: the model's 24 kHz PCM16 -> Float32 for an AudioBuffer.
 */

export const INPUT_RATE = 16_000;
export const OUTPUT_RATE = 24_000;
export const CHUNK_SAMPLES = 640; // 40 ms at 16 kHz

/** Linear-interpolating resampler with a simple box low-pass when downsampling. */
export function resample(input: Float32Array, fromRate: number, toRate: number = INPUT_RATE): Float32Array {
  if (fromRate === toRate) return input.slice();
  const ratio = fromRate / toRate;
  const outLength = Math.floor(input.length / ratio);
  const out = new Float32Array(outLength);
  const window = Math.max(1, Math.floor(ratio));
  for (let i = 0; i < outLength; i++) {
    const pos = i * ratio;
    if (window > 1) {
      // average the source samples this output sample covers (anti-aliasing)
      const start = Math.floor(pos);
      let sum = 0;
      let n = 0;
      for (let j = start; j < Math.min(input.length, start + window); j++) {
        sum += input[j];
        n++;
      }
      out[i] = n ? sum / n : 0;
    } else {
      const a = Math.floor(pos);
      const b = Math.min(a + 1, input.length - 1);
      const t = pos - a;
      out[i] = input[a] * (1 - t) + input[b] * t;
    }
  }
  return out;
}

export function floatToPcm16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff);
  }
  return out;
}

export function pcm16ToFloat(input: Int16Array): Float32Array {
  const out = new Float32Array(input.length);
  for (let i = 0; i < input.length; i++) out[i] = input[i] / (input[i] < 0 ? 0x8000 : 0x7fff);
  return out;
}

export function pcm16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

export function base64ToPcm16(b64: string): Int16Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Int16Array(bytes.buffer, 0, Math.floor(bytes.length / 2));
}

/** Accumulates resampled audio and emits fixed 40 ms PCM16 chunks. */
export class Chunker {
  private buf: number[] = [];
  private readonly fromRate: number;
  private readonly chunk: number;

  constructor(fromRate: number, chunk: number = CHUNK_SAMPLES) {
    this.fromRate = fromRate;
    this.chunk = chunk;
  }

  push(frame: Float32Array): Int16Array[] {
    const res = resample(frame, this.fromRate);
    for (let i = 0; i < res.length; i++) this.buf.push(res[i]);
    const out: Int16Array[] = [];
    while (this.buf.length >= this.chunk) out.push(floatToPcm16(Float32Array.from(this.buf.splice(0, this.chunk))));
    return out;
  }
}
