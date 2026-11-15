import './ui/styles.css';
import { createApp } from './app';

const root = document.getElementById('app');
if (!(root instanceof HTMLElement)) {
  throw new Error('Missing #app element');
}

const app = createApp(root);
app.start();

if (__TEST_HOOK__) {
  void import('./testhook/testhook').then(({ installTestHook }) => {
    installTestHook(app);
  });
}
