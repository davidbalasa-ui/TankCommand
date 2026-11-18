// The version lives in one place, package.json: the game shows it, saves record it, and the
// Android build (android/app/build.gradle) derives versionName and versionCode from it.
import { version } from '../../package.json';

export const APP_VERSION: string = version;
