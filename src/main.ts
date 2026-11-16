import './ui/styles.css';
import { createApp } from './app';

const root = document.getElementById('app');
if (!(root instanceof HTMLElement)) {
  throw new Error('Missing #app element');
}

const app = createApp(root);
app.start();

// Hand over from the loading splash in index.html once the first screen is up.
const splash = document.getElementById('splash');
if (splash) {
  window.requestAnimationFrame(() => {
    splash.classList.add('gone');
    window.setTimeout(() => {
      splash.remove();
    }, 400);
  });
}

if (__TEST_HOOK__) {
  void import('./testhook/testhook').then(({ installTestHook }) => {
    installTestHook(app);
  });
}
