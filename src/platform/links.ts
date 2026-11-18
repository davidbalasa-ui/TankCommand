import { Capacitor } from '@capacitor/core';

/** The privacy policy, a static page of the web build (public/privacy.html). Play Console links here. */
export const PRIVACY_POLICY_URL = 'https://tankcommand.vercel.app/privacy.html';

/**
 * The web build opens its own copy (so a local or preview build shows the policy it ships);
 * the Android app opens the published page, which Capacitor hands to the phone's browser
 * because it is not the app's own address.
 */
export function privacyPolicyUrl(): string {
  if (Capacitor.isNativePlatform() || typeof window === 'undefined') {
    return PRIVACY_POLICY_URL;
  }
  return new URL('./privacy.html', window.location.href).toString();
}

export function openPrivacyPolicy(): void {
  window.open(privacyPolicyUrl(), '_blank', 'noopener');
}
