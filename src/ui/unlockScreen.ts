import type { ScreenContext } from './router';
import { button } from './controls';
import { FREE_CONTENT } from '../data/fullGame';

/**
 * The "Full game" screen: what the one purchase adds, its price from Google Play, Buy, Restore
 * purchases and Back. Laid out as two short columns so everything fits a 915x412 phone.
 */
export function mountUnlock(root: HTMLElement, ctx: ScreenContext): () => void {
  const purchases = ctx.purchases;
  const body = document.createElement('div');
  body.className = 'unlock-body';

  const pitch = document.createElement('div');
  pitch.className = 'panel unlock-pitch';
  const lead = document.createElement('p');
  lead.className = 'unlock-lead';
  lead.textContent = 'Unlock every campaign mission and every skirmish map with one purchase.';
  const list = document.createElement('ul');
  list.className = 'unlock-list';
  const free = FREE_CONTENT.freeSkirmishMaps.length;
  for (const line of [
    `Free: all training, the first ${FREE_CONTENT.freeMissionsPerCampaign} missions of each campaign and ${free} skirmish maps.`,
    'Full game: both campaigns to the end and all skirmish maps.',
    'One payment. No ads, no subscription, no account.',
  ]) {
    const item = document.createElement('li');
    item.textContent = line;
    list.append(item);
  }
  pitch.append(lead, list);

  const side = document.createElement('div');
  side.className = 'unlock-side';
  const price = document.createElement('p');
  price.className = 'unlock-price';
  price.dataset.unlockPrice = 'true';
  const status = document.createElement('p');
  status.className = 'unlock-status';
  status.dataset.unlockStatus = 'true';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');

  let busy = false;
  let closed = false;
  const run = (job: () => Promise<{ status: string; message: string }>, pendingText: string): void => {
    if (busy || !purchases) {
      if (!purchases) {
        status.textContent = 'Purchases are unavailable in this environment.';
      }
      return;
    }
    busy = true;
    status.textContent = pendingText;
    status.dataset.result = 'pending';
    refresh();
    void job()
      .then((result) => {
        if (!closed) {
          status.textContent = result.message;
          status.dataset.result = result.status;
        }
      })
      .finally(() => {
        busy = false;
        if (!closed) {
          refresh();
        }
      });
  };

  const buy = button('unlock', 'buy', 'Buy full game', () => {
    run(() => purchases?.buy() ?? Promise.resolve({ status: 'error', message: '' }), 'Opening Google Play…');
  });
  buy.classList.add('primary');
  const restore = button('unlock', 'restore', 'Restore purchases', () => {
    run(() => purchases?.restore() ?? Promise.resolve({ status: 'error', message: '' }), 'Checking Google Play…');
  });
  const back = button('unlock', 'back', 'Back', () => {
    ctx.router.back();
  });

  let priceText: string | null = null;
  const refresh = (): void => {
    const unlocked = purchases?.isUnlocked() ?? false;
    const store = purchases?.canPurchase() ?? false;
    if (unlocked) {
      price.textContent = '✓ The full game is unlocked.';
    } else if (!store) {
      price.textContent = 'Available in the Android app from Google Play.';
    } else {
      price.textContent = priceText ? `Price: ${priceText}` : 'Price: loading from Google Play…';
    }
    buy.textContent = priceText && store && !unlocked ? `Buy full game · ${priceText}` : 'Buy full game';
    buy.disabled = busy || unlocked || !store;
    restore.disabled = busy;
    root.classList.toggle('unlocked', unlocked);
  };

  side.append(price, buy, restore, status);
  body.append(pitch, side);
  root.append(body, back);
  refresh();

  const unsubscribe = purchases?.subscribe(refresh);
  if (purchases?.canPurchase()) {
    void purchases.price().then((value) => {
      if (closed) {
        return;
      }
      priceText = value;
      if (!value && !purchases.isUnlocked()) {
        price.textContent = 'Price unavailable: Google Play could not be reached.';
        buy.textContent = 'Buy full game';
        return;
      }
      refresh();
    });
  }

  return () => {
    closed = true;
    unsubscribe?.();
  };
}
