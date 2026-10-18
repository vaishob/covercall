import test from 'node:test';
import assert from 'node:assert/strict';
import { base64ToPcm16, CHUNK_SAMPLES, Chunker, floatToPcm16, pcm16ToBase64, pcm16ToFloat, resample } from './pcm.ts';

test('resample 48 kHz to 16 kHz keeps a third of the samples and the signal level', () => {
  const input = new Float32Array(4800).fill(0.5);
  const out = resample(input, 48_000);
  assert.equal(out.length, 1600);
  assert.ok(out.every((v) => Math.abs(v - 0.5) < 1e-6));
});

test('resample 44.1 kHz to 16 kHz gives the right length; same rate is a copy', () => {
  assert.equal(resample(new Float32Array(4410), 44_100).length, 1600);
  const same = new Float32Array([0.1, 0.2]);
  assert.deepEqual(Array.from(resample(same, 16_000)), Array.from(same));
});

test('downsampling averages away a signal above the new Nyquist', () => {
  const alt = Float32Array.from({ length: 4800 }, (_, i) => (i % 2 ? 1 : -1)); // 24 kHz tone at 48 kHz
  const out = resample(alt, 48_000);
  assert.ok(Math.max(...Array.from(out).map(Math.abs)) <= 1 / 3 + 1e-6);
});

test('PCM16 conversion clamps and round-trips through base64', () => {
  const pcm = floatToPcm16(new Float32Array([-2, -1, 0, 1, 2]));
  assert.deepEqual(Array.from(pcm), [-32768, -32768, 0, 32767, 32767]);
  assert.deepEqual(Array.from(base64ToPcm16(pcm16ToBase64(pcm))), Array.from(pcm));
  assert.deepEqual(Array.from(pcm16ToFloat(new Int16Array([-32768, 0, 32767]))), [-1, 0, 1]);
});

test('Chunker emits 40 ms (640-sample) chunks at 16 kHz', () => {
  const c = new Chunker(48_000);
  assert.equal(c.push(new Float32Array(960)).length, 0); // 20 ms in, 320 samples buffered
  const chunks = c.push(new Float32Array(1920)); // +40 ms -> 960 buffered -> one chunk, 320 left
  assert.equal(chunks.length, 1);
  assert.equal(chunks[0].length, CHUNK_SAMPLES);
});
