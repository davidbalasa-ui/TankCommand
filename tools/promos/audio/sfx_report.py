"""Analysis helpers ('listen proxies'): numbers + spectrogram sheets for wavs / mp4 audio.

    python tools/promos/audio/sfx_report.py stats <dir|files...>
    python tools/promos/audio/sfx_report.py sheet <out.png> <files...>     # spectrogram grid
    python tools/promos/audio/sfx_report.py clip <mp4|wav> <out.png> [--marks t1,t2,...]
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np


def read_wav(path):
    with wave.open(path) as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768
    return x.reshape(-1, ch), sr


def read_any(path, sr=48000):
    if path.endswith('.wav'):
        return read_wav(path)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-f', 's16le', '-ac', '2', '-ar', str(sr), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, '<i2').astype(float).reshape(-1, 2) / 32768, sr


def bands(x, sr):
    m = x.mean(axis=1) if x.ndim == 2 else x
    X = np.abs(np.fft.rfft(m)) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    tot = X.sum() + 1e-20
    edges = [0, 60, 150, 500, 2000, 6000, sr / 2]
    return [10 * np.log10(X[(f >= a) & (f < b)].sum() / tot + 1e-12) for a, b in zip(edges[:-1], edges[1:])]


def stats(path):
    x, sr = read_any(path)
    pk = 20 * np.log10(np.max(np.abs(x)) + 1e-12)
    rms = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    b = bands(x, sr)
    # click check: largest sample-to-sample jump relative to peak
    jump = np.max(np.abs(np.diff(x, axis=0))) / (np.max(np.abs(x)) + 1e-12)
    corr = np.corrcoef(x[:, 0], x[:, 1])[0, 1] if x.shape[1] == 2 else 1
    return dict(dur=len(x) / sr, peak=pk, rms=rms, crest=pk - rms, bands=b, jump=jump, lr_corr=corr,
                start=np.max(np.abs(x[:16])), end=np.max(np.abs(x[-16:])))


def spec_png(path, out, w=640, h=220, extra=''):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-lavfi',
                    f'aformat=channel_layouts=mono,showspectrumpic=s={w}x{h}:legend=0:fscale=log:color=intensity:scale=log:drange=60{extra}',
                    out], check=True)


def wave_png(path, out, w=640, h=90):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-lavfi',
                    f'aformat=channel_layouts=mono,showwavespic=s={w}x{h}:split_channels=0:colors=0x66ccff:scale=lin',
                    out], check=True)


def sheet(out, files, cols=3, w=420, h=150):
    tmp = tempfile.mkdtemp()
    tiles = []
    for i, f in enumerate(files):
        a = os.path.join(tmp, f'{i}_s.png')
        b = os.path.join(tmp, f'{i}_w.png')
        c = os.path.join(tmp, f'{i}.png')
        spec_png(f, a, w, h)
        wave_png(f, b, w, 50)
        name = os.path.basename(f).replace('.wav', '')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', b, '-i', a, '-filter_complex',
                        f'[0][1]vstack,pad=iw:ih+18:0:18:black,drawtext=text=\'{name}\':x=4:y=2:fontsize=14:fontcolor=white',
                        c], check=True)
        tiles.append(c)
    n = len(tiles)
    rows = (n + cols - 1) // cols
    ins = []
    for t in tiles:
        ins += ['-i', t]
    th = h + 50 + 18
    lay = '|'.join(f'{(i % cols) * w}_{(i // cols) * th}' for i in range(n))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex',
                    ''.join(f'[{i}]' for i in range(n)) + f'xstack=inputs={n}:layout={lay}:fill=black', out], check=True)
    del rows
    return out


def clip_png(src, out, marks=(), seconds=6.0, w=1440):
    """Waveform + spectrogram of a clip's audio with event time marks (red ticks)."""
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, 'a.wav')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-vn', '-ac', '2', '-ar', '48000', wav], check=True)
    a, b = os.path.join(tmp, 's.png'), os.path.join(tmp, 'w.png')
    spec_png(wav, a, w, 300)
    wave_png(wav, b, w, 140)
    draw = ','.join(f"drawbox=x={int(t / seconds * w)}:y=0:w=2:h=ih:color=red@0.8:t=fill" for t in marks) or 'null'
    grid = ','.join(f"drawbox=x={int(s / seconds * w)}:y=0:w=1:h=12:color=white@0.9:t=fill" for s in range(int(seconds) + 1))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', b, '-i', a, '-filter_complex',
                    f'[0][1]vstack,{draw},{grid}', out], check=True)
    return out


def main():
    cmd = sys.argv[1]
    if cmd == 'stats':
        files = []
        for p in sys.argv[2:]:
            files += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith('.wav')) if os.path.isdir(p) else [p]
        print(f"{'file':28s} {'dur':>5s} {'peak':>6s} {'rms':>6s} {'crest':>5s}  <60  60-150 150-500 .5-2k 2-6k  >6k   jump  lrcorr")
        for f in files:
            s = stats(f)
            print(f"{os.path.basename(f)[:28]:28s} {s['dur']:5.2f} {s['peak']:6.1f} {s['rms']:6.1f} {s['crest']:5.1f} "
                  + ' '.join(f'{v:5.1f}' for v in s['bands']) + f"  {s['jump']:.2f}  {s['lr_corr']:.2f}")
    elif cmd == 'sheet':
        sheet(sys.argv[2], sys.argv[3:])
    elif cmd == 'clip':
        marks = []
        if '--marks' in sys.argv:
            marks = [float(v) for v in sys.argv[sys.argv.index('--marks') + 1].split(',') if v]
        clip_png(sys.argv[2], sys.argv[3], marks)


if __name__ == '__main__':
    main()
