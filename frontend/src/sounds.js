// Tiny WebAudio synth: no audio files needed. Shared context, created on first user gesture.
let ctx;
const ac = () => (ctx ||= new (window.AudioContext || window.webkitAudioContext)());
export const audioContext = ac;

function tone(freq, start, dur, vol = 0.08, type = "sine") {
  const c = ac(), o = c.createOscillator(), g = c.createGain();
  o.type = type; o.frequency.value = freq;
  g.gain.setValueAtTime(0, c.currentTime + start);
  g.gain.linearRampToValueAtTime(vol, c.currentTime + start + 0.02);
  g.gain.linearRampToValueAtTime(0, c.currentTime + start + dur);
  o.connect(g).connect(c.destination);
  o.start(c.currentTime + start); o.stop(c.currentTime + start + dur + 0.05);
}

let ringTimer;
export function ringStart() {
  ringStop();
  const burst = () => { tone(440, 0, 0.9, 0.06); tone(480, 0, 0.9, 0.06); };
  burst(); ringTimer = setInterval(burst, 2400);
}
export function ringStop() { clearInterval(ringTimer); ringTimer = null; }
export const chime = () => { tone(660, 0, 0.12); tone(880, 0.12, 0.2); };
export const endTone = () => { tone(520, 0, 0.14); tone(390, 0.16, 0.14); tone(260, 0.32, 0.3); };
