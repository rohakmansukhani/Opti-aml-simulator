'use client';
import { createTheme } from '@mui/material/styles';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });

export const theme = createTheme({
    palette: {
        mode: 'light',
        primary: {
            main: '#0F172A', // Deep Navy
            light: '#334155',
            dark: '#020617',
        },
        secondary: {
            main: '#2563EB', // Electric Blue
            light: '#60A5FA',
            dark: '#1D4ED8',
        },
        background: {
            default: '#F8FAFC', // Slate 50
            paper: '#FFFFFF',
        },
        text: {
            primary: '#0F172A',
            secondary: '#64748B',
        },
    },
    typography: {
        fontFamily: inter.style.fontFamily,
        h1: { fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em' },
        h2: { fontSize: '2rem', fontWeight: 600, letterSpacing: '-0.01em' },
        h3: { fontSize: '1.5rem', fontWeight: 600 },
        button: { textTransform: 'none', fontWeight: 500 },
    },
    shape: {
        borderRadius: 12,
    },
    components: {
        MuiButton: {
            styleOverrides: {
                root: {
                    borderRadius: '8px',
                    boxShadow: 'none',
                    '&:hover': {
                        boxShadow: 'none',
                    },
                },
                containedPrimary: {
                    background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
                },
                containedSecondary: {
                    background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
                }
            },
        },
        MuiPaper: {
            styleOverrides: {
                root: {
                    backgroundImage: 'none',
                },
                elevation1: {
                    boxShadow: '0px 1px 3px rgba(0,0,0,0.05), 0px 1px 2px rgba(0,0,0,0.1)',
                    border: '1px solid #E2E8F0',
                },
            },
        },
    },
});
