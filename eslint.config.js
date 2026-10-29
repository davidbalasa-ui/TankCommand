import tseslint from 'typescript-eslint';

const baseConfigs = tseslint.configs.recommendedTypeChecked.map((config) => ({
  ...config,
  files: ['src/**/*.ts'],
}));

export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'android/**',
      'node_modules/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'tests/**',
      'scripts/**',
      'public/**',
      '*.config.*',
      'eslint.config.js',
    ],
  },
  ...baseConfigs,
  {
    files: ['src/**/*.ts'],
    languageOptions: {
      parserOptions: {
        projectService: {
          allowDefaultProject: ['src/sim/bad.ts', 'src/render/ok.ts'],
        },
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  {
    files: ['src/sim/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: [
                'three',
                'three/*',
                '@capacitor',
                '@capacitor/*',
                '**/render/**',
                '**/ui/**',
                '**/platform/**',
                '**/assets/**',
                '../render',
                '../render/*',
                '../ui',
                '../ui/*',
                '../platform',
                '../platform/*',
                '../assets',
                '../assets/*',
              ],
              message: 'src/sim must stay headless and dependency-free.',
            },
          ],
        },
      ],
      'no-restricted-globals': [
        'error',
        { name: 'window', message: 'src/sim must not touch browser globals.' },
        { name: 'document', message: 'src/sim must not touch browser globals.' },
        { name: 'localStorage', message: 'src/sim must not touch browser globals.' },
        { name: 'performance', message: 'src/sim must not read clocks.' },
      ],
      'no-restricted-properties': [
        'error',
        { object: 'Math', property: 'random', message: 'src/sim must use the seeded RNG.' },
        { object: 'Date', property: 'now', message: 'src/sim must not read clocks.' },
        { object: 'performance', property: 'now', message: 'src/sim must not read clocks.' },
      ],
    },
  },
);
