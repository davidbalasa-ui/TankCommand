// The opening film: plays once on first launch (skippable) and again from the title's Intro button.
// It is a plain <video> over everything; the film itself has no words or sound.

const FILM_URL = 'film/opening.mp4';
const SEEN_KEY = 'tc.introSeen';

let playing: Promise<void> | null = null;

/** True when the film has not been shown on this device yet (automated browsers never get it). */
export function introFilmDue(): boolean {
  if (typeof navigator !== 'undefined' && navigator.webdriver) {
    return false;
  }
  try {
    return window.localStorage.getItem(SEEN_KEY) !== '1';
  } catch {
    return false;
  }
}

function markSeen(): void {
  try {
    window.localStorage.setItem(SEEN_KEY, '1');
  } catch {
    // No storage: it will simply play again next launch.
  }
}

/** Plays the film full screen; resolves when it ends, is skipped or cannot play. */
export function playIntroFilm(): Promise<void> {
  if (playing) {
    return playing;
  }
  playing = new Promise<void>((resolve) => {
    const layer = document.createElement('div');
    layer.className = 'intro-film';
    const video = document.createElement('video');
    video.className = 'intro-film-video';
    video.src = FILM_URL;
    video.muted = true;
    video.playsInline = true;
    video.autoplay = true;
    video.preload = 'auto';
    video.setAttribute('playsinline', '');
    const skip = document.createElement('button');
    skip.type = 'button';
    skip.className = 'intro-film-skip';
    skip.dataset.testid = 'intro-skip';
    skip.textContent = 'Skip';
    skip.setAttribute('aria-label', 'Skip intro');
    layer.append(video, skip);

    let done = false;
    let hideTimer = 0;
    const finish = (): void => {
      if (done) {
        return;
      }
      done = true;
      markSeen();
      window.clearTimeout(hideTimer);
      window.removeEventListener('keydown', onKey);
      video.pause();
      layer.classList.add('leaving');
      window.setTimeout(() => {
        video.removeAttribute('src');
        video.load();
        layer.remove();
        playing = null;
        resolve();
      }, 350);
    };
    // The skip button shows on any tap and fades again after a few seconds.
    const showSkip = (): void => {
      layer.classList.add('show-skip');
      window.clearTimeout(hideTimer);
      hideTimer = window.setTimeout(() => {
        layer.classList.remove('show-skip');
      }, 3000);
    };
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        finish();
      }
    };
    skip.addEventListener('click', (event) => {
      event.stopPropagation();
      finish();
    });
    layer.addEventListener('pointerdown', showSkip);
    window.addEventListener('keydown', onKey);
    video.addEventListener('ended', finish);
    video.addEventListener('error', finish);
    document.body.append(layer);
    showSkip();
    video.play().catch(() => {
      finish();
    });
  });
  return playing;
}
