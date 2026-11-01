import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { BenchmarkProvider } from '../components/benchmark-provider';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://mario.nicholasg.com'),
  title: 'mario bench',
  alternates: { canonical: '/' },
  description: 'Mario benchmark with playable World 1-1 and recorded demo runs.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body className={`${GeistSans.variable} ${GeistMono.variable}`}><BenchmarkProvider>{children}</BenchmarkProvider></body></html>;
}
