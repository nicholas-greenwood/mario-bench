import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://mario.nicholasg.com'),
  title: 'mario bench',
  alternates: { canonical: '/' },
  description: 'decision models play super mario bros. world 1-1. watch recorded, offline-verified development runs and play the level yourself.',
};

const themeScript = `try{var t=localStorage.getItem('mario-bench-theme');document.documentElement.dataset.theme=t==='dark'||t==='light'?t:(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-GB" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body className={`${GeistSans.variable} ${GeistMono.variable}`}>{children}</body>
    </html>
  );
}
