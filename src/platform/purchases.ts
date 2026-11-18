import { Capacitor } from '@capacitor/core';
import { Preferences } from '@capacitor/preferences';
import { NativePurchases, PURCHASE_TYPE, type Transaction } from '@capgo/native-purchases';

/** The one in-app product: a non-consumable "full game unlock" (Play Console product id). */
export const FULL_GAME_PRODUCT_ID = 'full_game_unlock';

/** Preferences key of the cached unlock flag (backed up with the other preferences). */
export const UNLOCK_FLAG_KEY = 'purchase.fullGameUnlock';

/** What the game needs from the store; the default talks to Google Play Billing. */
export interface StoreBackend {
  /** The localised price ("€4.99"), or null when the store has no such product. */
  price(): Promise<string | null>;
  /** Starts the Play purchase sheet for the product. */
  buy(): Promise<'purchased' | 'pending'>;
  /** Asks Play which products this account owns: true when it owns the unlock. */
  owned(): Promise<boolean>;
}

/** Where the cached flag lives (Preferences in the app). */
export interface FlagStore {
  get(): Promise<boolean>;
  set(value: boolean): Promise<void>;
}

export type PurchaseStatus = 'unlocked' | 'cancelled' | 'pending' | 'notOwned' | 'unavailable' | 'error';

export interface PurchaseResult {
  status: PurchaseStatus;
  message: string;
}

export interface PurchasesDeps {
  isNative?: boolean;
  backend?: StoreBackend;
  flag?: FlagStore;
}

function errorText(error: unknown): string {
  if (error && typeof error === 'object') {
    const record = error as { code?: unknown; message?: unknown };
    return `${typeof record.code === 'string' ? record.code : ''} ${typeof record.message === 'string' ? record.message : ''}`;
  }
  return String(error);
}

function ownsUnlock(purchase: Transaction): boolean {
  if (purchase.productIdentifier !== FULL_GAME_PRODUCT_ID) {
    return false;
  }
  // Android reports purchaseState as Purchase.PurchaseState ("1" purchased, "2" pending).
  const state = purchase.purchaseState;
  return state === undefined || state === '1' || state === 'PURCHASED';
}

/** Google Play Billing through @capgo/native-purchases. */
export const playStoreBackend: StoreBackend = {
  async price() {
    const { products } = await NativePurchases.getProducts({
      productIdentifiers: [FULL_GAME_PRODUCT_ID],
      productType: PURCHASE_TYPE.INAPP,
    });
    const product = products.find((item) => item.identifier === FULL_GAME_PRODUCT_ID);
    return product?.priceString || null;
  },
  async buy() {
    const transaction = await NativePurchases.purchaseProduct({
      productIdentifier: FULL_GAME_PRODUCT_ID,
      productType: PURCHASE_TYPE.INAPP,
      quantity: 1,
      isConsumable: false,
      autoAcknowledgePurchases: true,
    });
    return transaction.purchaseState === '2' || transaction.purchaseState === 'PENDING' ? 'pending' : 'purchased';
  },
  async owned() {
    // restorePurchases also acknowledges a purchase left unacknowledged (app closed mid-purchase).
    await NativePurchases.restorePurchases();
    const { purchases } = await NativePurchases.getPurchases({ productType: PURCHASE_TYPE.INAPP });
    return purchases.some(ownsUnlock);
  },
};

const preferencesFlag: FlagStore = {
  async get() {
    const { value } = await Preferences.get({ key: UNLOCK_FLAG_KEY });
    return value === 'true';
  },
  async set(value) {
    await Preferences.set({ key: UNLOCK_FLAG_KEY, value: value ? 'true' : 'false' });
  },
};

/**
 * The "full game unlock" purchase.
 *
 * In the Android app `isUnlocked()` answers from a flag cached in Preferences, so it works offline
 * and at once; `init()` loads that flag and then asks Google Play (restore) in the background, so a
 * purchase made on another device, or a refund, is picked up at the next start. Only an answer
 * from Play changes the flag: when Play cannot be reached the cached flag stands.
 *
 * On the web everything is unlocked (the web build is the free demo and test site). The test hook
 * can override the state on any platform to exercise the locked screens.
 */
export class PurchaseService {
  private readonly isNative: boolean;
  private readonly backend: StoreBackend;
  private readonly flag: FlagStore;
  private unlocked = false;
  private testOverride: boolean | null = null;
  private cachedPrice: string | null = null;
  private readonly listeners = new Set<() => void>();
  /** Store calls run one after another: the billing client does not take concurrent calls. */
  private queue: Promise<unknown> = Promise.resolve();

  constructor(deps: PurchasesDeps = {}) {
    this.isNative = deps.isNative ?? Capacitor.isNativePlatform();
    this.backend = deps.backend ?? playStoreBackend;
    this.flag = deps.flag ?? preferencesFlag;
  }

  /** Loads the cached flag and, in the app, refreshes it from Play without blocking the caller. */
  async init(): Promise<void> {
    if (!this.isNative) {
      return;
    }
    try {
      await this.setUnlocked(await this.flag.get(), false);
    } catch {
      // No stored flag: stays locked until Play answers.
    }
    void this.serial(() => this.refresh());
  }

  isUnlocked(): boolean {
    if (this.testOverride !== null) {
      return this.testOverride;
    }
    return this.isNative ? this.unlocked : true;
  }

  /** True where purchases can be made (the Android app). */
  canPurchase(): boolean {
    return this.isNative;
  }

  /** The store price, or null when it is not known (web, offline, product not set up). */
  async price(): Promise<string | null> {
    if (!this.isNative) {
      return null;
    }
    return this.serial(async () => {
      try {
        this.cachedPrice = (await this.backend.price()) ?? this.cachedPrice;
      } catch {
        // Keep the last known price.
      }
      return this.cachedPrice;
    });
  }

  buy(): Promise<PurchaseResult> {
    return this.serial(async (): Promise<PurchaseResult> => {
      if (!this.isNative) {
        return { status: 'unavailable', message: 'The full game is bought in the Android app from Google Play.' };
      }
      try {
        const outcome = await this.backend.buy();
        if (outcome === 'pending') {
          return {
            status: 'pending',
            message: 'Your payment is pending. The full game unlocks once Google Play confirms it.',
          };
        }
        await this.setUnlocked(true);
        return { status: 'unlocked', message: 'Thank you! The full game is unlocked.' };
      } catch (error) {
        const text = errorText(error);
        if (/USER_CANCEL/i.test(text)) {
          return { status: 'cancelled', message: 'Purchase cancelled.' };
        }
        if (/ALREADY_OWNED/i.test(text)) {
          await this.setUnlocked(true);
          return { status: 'unlocked', message: 'You already own the full game. It is unlocked.' };
        }
        if (/pending/i.test(text)) {
          return {
            status: 'pending',
            message: 'Your payment is pending. The full game unlocks once Google Play confirms it.',
          };
        }
        if (/BILLING_UNAVAILABLE|SERVICE_UNAVAILABLE|SERVICE_DISCONNECTED|NETWORK_ERROR/i.test(text)) {
          return { status: 'unavailable', message: 'Google Play could not be reached. Check your connection and try again.' };
        }
        return { status: 'error', message: 'The purchase did not go through. Please try again.' };
      }
    });
  }

  restore(): Promise<PurchaseResult> {
    return this.serial(async (): Promise<PurchaseResult> => {
      if (!this.isNative) {
        return this.isUnlocked()
          ? { status: 'unlocked', message: 'Everything is unlocked in the web version.' }
          : { status: 'unavailable', message: 'Purchases are restored in the Android app.' };
      }
      return this.refresh();
    });
  }

  /** Test hook only: forces the unlocked state (null returns to the real one). */
  setTestOverride(value: boolean | null): void {
    this.testOverride = value;
    this.notify();
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private async refresh(): Promise<PurchaseResult> {
    let owned: boolean;
    try {
      owned = await this.backend.owned();
    } catch {
      return {
        status: 'unavailable',
        message: 'Google Play could not be reached, so nothing changed. Try again when you are online.',
      };
    }
    await this.setUnlocked(owned);
    return owned
      ? { status: 'unlocked', message: 'Purchase restored. The full game is unlocked.' }
      : { status: 'notOwned', message: 'No full game purchase was found for this Google account.' };
  }

  private serial<T>(job: () => Promise<T>): Promise<T> {
    const run = this.queue.then(job, job);
    this.queue = run.catch(() => undefined);
    return run;
  }

  private async setUnlocked(value: boolean, persist = true): Promise<void> {
    const changed = this.unlocked !== value;
    this.unlocked = value;
    if (persist) {
      try {
        await this.flag.set(value);
      } catch {
        // The flag is a cache: Play is asked again at the next start.
      }
    }
    if (changed) {
      this.notify();
    }
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}
