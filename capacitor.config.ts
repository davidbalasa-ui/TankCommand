import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.davidbalasa.tankcommand',
  appName: 'TankCommand',
  webDir: 'dist',
  android: {
    backgroundColor: '#090D16',
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 0,
    },
  },
};

export default config;
