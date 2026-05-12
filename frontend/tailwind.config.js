/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0D1117',
        'bg-secondary': '#161B22',
        border: '#30363D',
        'accent-cyan': '#58A6FF',
        'accent-green': '#3FB950',
        'accent-red': '#F85149',
        'accent-orange': '#D29922',
        'text-primary': '#E6EDF3',
        'text-muted': '#8B949E',
      },
      fontFamily: {
        heading: ['"JetBrains Mono"', 'monospace'],
        body: ['"IBM Plex Mono"', 'monospace'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      boxShadow: {
        cyan: '0 0 10px rgba(88,166,255,0.3)',
        'cyan-lg': '0 0 20px rgba(88,166,255,0.5)',
      },
    },
  },
  plugins: [],
}
